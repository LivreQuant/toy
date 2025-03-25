#!/bin/bash
echo "Initializing database schemas and data..."

# Apply database schema and data ConfigMaps
kubectl apply -f ./k8s/config/db-schemas.yaml
kubectl apply -f ./k8s/config/db-data.yaml

# Initialize database with the job
kubectl apply -f ./k8s/jobs/db-init-job.yaml

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