#!/bin/bash
# 02I-build-exchange-service.sh (renamed from deploy to build)
echo "Building exchange service image..."

# Get the correct path to the directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
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
if [[ "$REBUILD" == "true" ]] || ! docker images opentp/exchange-service:latest --format "{{.Repository}}:{{.Tag}}" | grep -q "opentp/exchange-service:latest"; then
    echo "Building exchange-service Docker image..."
    cd "$BACKEND_DIR/exchange-service"
    if [[ "$REBUILD" == "true" ]]; then
        echo "Rebuilding without cache..."
        docker build --no-cache -t opentp/exchange-service:latest .
    else
        docker build -t opentp/exchange-service:latest .
    fi
    
    if [ $? -ne 0 ]; then
        echo "Error: Failed to build exchange-service image"
        exit 1
    fi
    
    echo "Exchange service image built successfully"
    cd - > /dev/null
else
    echo "Using existing exchange-service image"
fi

# REMOVED: kubectl apply - orchestrator will handle deployment now
echo "Exchange service image ready for orchestrator deployment"