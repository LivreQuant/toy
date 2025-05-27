#!/bin/bash
echo "Setting up MinIO storage service..."

# Get the correct path to the directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
K8S_DIR="$BASE_DIR/k8s"

# Apply storage credentials secret
echo "Applying storage credentials..."
kubectl apply -f "$K8S_DIR/secrets/storage-credentials.yaml"

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
kubectl exec $MINIO_POD -- mc alias set local http://localhost:9000 convictions-storage conviction-storage-secret-2024
kubectl exec $MINIO_POD -- mc mb local/conviction-files --ignore-existing

# Create subdirectories structure
echo "Setting up bucket structure..."
kubectl exec $MINIO_POD -- mc cp /dev/null local/conviction-files/research/.keep
kubectl exec $MINIO_POD -- mc cp /dev/null local/conviction-files/convictions/.keep
kubectl exec $MINIO_POD -- mc cp /dev/null local/conviction-files/temp/.keep

echo "Storage service setup completed successfully!"
echo "MinIO Console: http://trading.local/storage (add to ingress)"
echo "Access Key: convictions-storage"
echo "Secret Key: conviction-storage-secret-2024"