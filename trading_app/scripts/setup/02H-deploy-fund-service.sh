#!/bin/bash
echo "Deploying fund service..."

# Get the correct path to the directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
K8S_DIR="$BASE_DIR/k8s"
BACKEND_DIR="$BASE_DIR/../backend"

# Parse arguments
REBUILD=false
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --rebuild) REBUILD=true ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Point to Minikube's Docker daemon
eval $(minikube docker-env)

# Check if image exists or rebuild is requested
if [[ "$REBUILD" == "true" ]] || ! docker images opentp/fund-service:latest --format "{{.Repository}}:{{.Tag}}" | grep -q "opentp/fund-service:latest"; then
    echo "Building fund-service Docker image..."
    cd "$BACKEND_DIR/fund-service"
    if [[ "$REBUILD" == "true" ]]; then
        echo "Rebuilding without cache..."
        docker build --no-cache -t opentp/fund-service:latest .
    else
        docker build -t opentp/fund-service:latest .
    fi
    
    if [ $? -ne 0 ]; then
        echo "Error: Failed to build fund-service image"
        exit 1
    fi
    
    echo "Fund service image built successfully"
    cd - > /dev/null
else
    echo "Using existing fund-service image"
fi

# Apply the service
kubectl apply -f "$K8S_DIR/deployments/fund-service.yaml"

# Check status
echo "Waiting for fund-service pods to start..."
kubectl get pods -l app=fund-service