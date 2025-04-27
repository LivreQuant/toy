#!/bin/bash
echo "Deploying session service..."

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
if [[ "$REBUILD" == "true" ]] || ! docker images opentp/session-service:latest --format "{{.Repository}}:{{.Tag}}" | grep -q "opentp/session-service:latest"; then
    echo "Building session-service Docker image..."
    cd "$BACKEND_DIR/session-service"
    if [[ "$REBUILD" == "true" ]]; then
        echo "Rebuilding without cache..."
        docker build --no-cache -t opentp/session-service:latest .
    else
        docker build -t opentp/session-service:latest .
    fi
    
    if [ $? -ne 0 ]; then
        echo "Error: Failed to build session-service image"
        exit 1
    fi
    
    echo "Session service image built successfully"
    cd - > /dev/null
else
    echo "Using existing session-service image"
fi

# Apply RBAC resources first
kubectl apply -f "$K8S_DIR/deployments/session-service-rbac.yaml"

# Apply the service
kubectl apply -f "$K8S_DIR/deployments/session-service.yaml"

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

# Check session service pod status
if ! check_pod_status "session-service"; then
    echo "Failed to deploy session-service"
    exit 1
fi

echo "Session service deployment completed successfully"

# Check status
echo "Waiting for session-service pods to start..."
kubectl get pods -l app=session-service