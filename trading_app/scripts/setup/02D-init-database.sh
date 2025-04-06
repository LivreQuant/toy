#!/bin/bash
echo "Initializing database schemas and data..."

# Get the correct path to the k8s directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
K8S_DIR="$BASE_DIR/k8s"

# Apply database schema and data ConfigMaps
kubectl apply -f "$K8S_DIR/config/db-schemas.yaml"
kubectl apply -f "$K8S_DIR/config/db-data.yaml"

# Initialize database with the job
kubectl apply -f "$K8S_DIR/jobs/db-init-job.yaml"

# Wait for job to complete
echo "Waiting for database initialization job to complete..."
kubectl wait --for=condition=complete job/db-init-job --timeout=120s

# Check if job succeeded
if [ $? -ne 0 ]; then
    echo "Database initialization failed. Checking logs..."
    pod_name=$(kubectl get pods -l job-name=db-init-job -o jsonpath="{.items[0].metadata.name}")
    kubectl logs $pod_name
    exit 1
fi

echo "Database initialization completed successfully."