#!/bin/bash
echo "Deploying risk model service..."

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
if [[ "$REBUILD" == "true" ]] || ! docker images opentp/risk-model-service:latest --format "{{.Repository}}:{{.Tag}}" | grep -q "opentp/risk-model-service:latest"; then
    echo "Building risk-model-service Docker image..."
    cd "$BACKEND_DIR/risk-model-service"
    if [[ "$REBUILD" == "true" ]]; then
        echo "Rebuilding without cache..."
        docker build --no-cache -t opentp/risk-model-service:latest .
    else
        docker build -t opentp/risk-model-service:latest .
    fi
    
    if [ $? -ne 0 ]; then
        echo "Error: Failed to build risk-model-service image"
        exit 1
    fi
    
    echo "risk-model service image built successfully"
    cd - > /dev/null
else
    echo "Using existing risk-model-service image"
fi

# Apply the service
kubectl apply -f "$K8S_DIR/deployments/risk-model-service.yaml"

# Function to check pod status
check_pod_status() {
    local service_name="$1"
    local max_attempts=30
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        # Get all pods for the service
        pods=$(kubectl get pods -l app="$service_name" --no-headers)
        
        # Check if pods exist
        if [ -z "$pods" ]; then
            echo "No pods found for $service_name"
            return 1
        fi

        # Check pod statuses
        error_pods=$(echo "$pods" | grep -E "Error|CrashLoopBackOff")
        running_pods=$(echo "$pods" | grep "Running")
        
        if [ -n "$error_pods" ]; then
            echo "Error: Some $service_name pods are in an error state:"
            echo "$error_pods"
            
            # Print logs for error pods
            echo -e "\nError Pod Logs:"
            echo "$error_pods" | while read -r pod rest; do
                echo -e "\n--- Logs for pod $pod ---"
                kubectl logs "$pod"
            done
            
            return 1
        fi

        # Check if all pods are running
        total_pods=$(echo "$pods" | wc -l)
        ready_pods=$(echo "$pods" | grep "1/1" | wc -l)

        if [ "$total_pods" -eq "$ready_pods" ]; then
            echo "All $service_name pods are running successfully"
            return 0
        fi

        # Wait and increment attempt
        echo "Waiting for $service_name pods to be ready (Attempt $((attempt+1))/$max_attempts)..."
        sleep 5
        ((attempt++))
    done

    echo "Timeout: $service_name pods did not become ready"
    return 1
}

# Check risk-model service pod status
if ! check_pod_status "risk-model-service"; then
    echo "Failed to deploy risk-model-service"
    exit 1
fi

echo "risk-model service deployment completed successfully"

# Check status
echo "Waiting for risk-model-service pods to start..."
kubectl get pods -l app=risk-model-service