#!/bin/bash
echo "Building exchange simulator image..."

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
if [[ "$REBUILD" == "true" ]] || ! docker images opentp/exchange-simulator:latest --format "{{.Repository}}:{{.Tag}}" | grep -q "opentp/exchange-simulator:latest"; then
    echo "Building exchange-simulator Docker image..."
    cd "$BACKEND_DIR/exchange-service"
    if [[ "$REBUILD" == "true" ]]; then
        echo "Rebuilding without cache..."
        docker build --no-cache -t opentp/exchange-simulator:latest .
    else
        docker build -t opentp/exchange-simulator:latest .
    fi
    
    if [ $? -ne 0 ]; then
        echo "Error: Failed to build exchange-simulator image"
        exit 1
    fi
    
    echo "Exchange simulator image built successfully"
    cd - > /dev/null
else
    echo "Using existing exchange-simulator image"
fi

# Apply the service account and config
kubectl apply -f "$K8S_DIR/deployments/exchange-simulator.yaml"

echo "Exchange simulator setup completed successfully"