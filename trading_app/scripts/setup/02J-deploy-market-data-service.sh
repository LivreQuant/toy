#!/bin/bash
echo "Deploying market data service..."

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
if [[ "$REBUILD" == "true" ]] || ! docker images opentp/market-data-service:latest --format "{{.Repository}}:{{.Tag}}" | grep -q "opentp/market-data-service:latest"; then
    echo "Building market-data-service Docker image..."
    cd "$BACKEND_DIR/market-data-service"
    if [[ "$REBUILD" == "true" ]]; then
        echo "Rebuilding without cache..."
        docker build --no-cache -t opentp/market-data-service:latest .
    else
        docker build -t opentp/market-data-service:latest .
    fi
    
    # Check build status
    if [ $? -ne 0 ]; then
        echo "Error: Failed to build market-data-service image"
        exit 1
    fi
    
    echo "Market data service image built successfully"
    cd - > /dev/null
else
    echo "Using existing market-data-service image"
fi

# Apply the service
kubectl apply -f "$K8S_DIR/deployments/market-data-service.yaml"

# Check status
echo "Waiting for market-data-service pods to start..."
kubectl get pods -l app=market-data-service