#!/bin/bash
echo "Deploying authentication service..."

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
if [[ "$REBUILD" == "true" ]] || ! docker images opentp/auth-service:latest --format "{{.Repository}}:{{.Tag}}" | grep -q "opentp/auth-service:latest"; then
    echo "Building auth-service Docker image..."
    cd "$BACKEND_DIR/authorization-service"
    if [[ "$REBUILD" == "true" ]]; then
        echo "Rebuilding without cache..."
        docker build --no-cache -t opentp/auth-service:latest .
    else
        docker build -t opentp/auth-service:latest .
    fi
    
    # Check build status
    if [ $? -ne 0 ]; then
        echo "Error: Failed to build auth-service image"
        exit 1
    fi
    
    echo "Auth service image built successfully"
    cd - > /dev/null
else
    echo "Using existing auth-service image"
fi

# Apply the service
kubectl apply -f "$K8S_DIR/deployments/auth-service.yaml"

# Check status
echo "Waiting for auth-service pods to start..."
kubectl get pods -l app=auth-service