#!/bin/bash
echo "Deploying order service..."

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
if [[ "$REBUILD" == "true" ]] || ! docker images opentp/order-service:latest --format "{{.Repository}}:{{.Tag}}" | grep -q "opentp/order-service:latest"; then
    echo "Building order-service Docker image..."
    cd "$BACKEND_DIR/order-service"
    if [[ "$REBUILD" == "true" ]]; then
        echo "Rebuilding without cache..."
        docker build --no-cache -t opentp/order-service:latest .
    else
        docker build -t opentp/order-service:latest .
    fi
    
    if [ $? -ne 0 ]; then
        echo "Error: Failed to build order-service image"
        exit 1
    fi
    
    echo "Order service image built successfully"
    cd - > /dev/null
else
    echo "Using existing order-service image"
fi

# Apply the service
kubectl apply -f "$K8S_DIR/deployments/order-service.yaml"

# Check status
echo "Waiting for order-service pods to start..."
kubectl get pods -l app=order-service -w