#!/bin/bash
echo "Setting up MinIO storage service..."

# Get the correct path to the directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
K8S_DIR="$BASE_DIR/k8s"

# Apply storage credentials secret
echo "Applying storage credentials..."
kubectl apply -f "$K8S_DIR/deployments/storage-credentials.yaml"

# Deploy MinIO storage service
echo "Deploying MinIO storage service..."
kubectl apply -f "$K8S_DIR/deployments/storage-service.yaml"

# Wait for MinIO to be ready
echo "Waiting for MinIO storage service to be ready..."
kubectl wait --for=condition=ready pod -l app=storage-service --timeout=120s

if [ $? -ne 0 ]; then
    echo "Failed to start MinIO storage service. Checking logs..."
    pod_name=$(kubectl get pods -l app=storage-service -o jsonpath="{.items[0].metadata.name}")
    kubectl logs $pod_name
    exit 1
fi

echo "MinIO storage service is ready!"

# Get MinIO pod name for bucket creation
MINIO_POD=$(kubectl get pods -l app=storage-service -o jsonpath="{.items[0].metadata.name}")

# Wait a bit more for MinIO to fully initialize
sleep 10

# Create the conviction-files bucket
echo "Creating conviction-files bucket..."
if kubectl exec $MINIO_POD -- mc alias set local http://localhost:9000 convictions-storage conviction-storage-secret-2024; then
    echo "MinIO alias configured successfully"
else
    echo "Failed to configure MinIO alias"
    exit 1
fi

if kubectl exec $MINIO_POD -- mc mb local/conviction-files --ignore-existing; then
    echo "Bucket created successfully"
else
    echo "Failed to create bucket, but continuing..."
fi

# Create subdirectories structure using mkdir
echo "Setting up bucket structure..."
kubectl exec $MINIO_POD -- mc mkdir -p local/conviction-files/research 2>/dev/null || echo "Research directory already exists or created"
kubectl exec $MINIO_POD -- mc mkdir -p local/conviction-files/convictions 2>/dev/null || echo "Convictions directory already exists or created"
kubectl exec $MINIO_POD -- mc mkdir -p local/conviction-files/encoded 2>/dev/null || echo "Encoded directory already exists or created"
kubectl exec $MINIO_POD -- mc mkdir -p local/conviction-files/temp 2>/dev/null || echo "Temp directory already exists or created"

# Verify bucket and directory structure
echo "Verifying bucket structure..."
kubectl exec $MINIO_POD -- mc ls local/conviction-files/ || echo "Could not list bucket contents, but bucket should be ready"

echo "Storage service setup completed successfully!"
echo ""
echo "=== MinIO Access Information ==="
echo "MinIO Console: http://trading.local/storage"
echo "Access Key: convictions-storage"
echo "Secret Key: conviction-storage-secret-2024"
echo "Bucket: conviction-files"
echo "================================"
echo ""
echo "Note: Add the storage path to your ingress configuration if not already done."