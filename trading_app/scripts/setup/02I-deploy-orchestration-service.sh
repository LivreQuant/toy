#!/bin/bash
# 02J-deploy-orchestrator-service.sh
echo "Building and deploying orchestrator service..."

# Get the correct path to the directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
K8S_DIR="$BASE_DIR/k8s"
ORCHESTRATOR_DIR="$BASE_DIR/orchestrator-service"

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

# Build orchestrator image
if [[ "$REBUILD" == "true" ]] || ! docker images opentp/orchestrator-service:latest --format "{{.Repository}}:{{.Tag}}" | grep -q "opentp/orchestrator-service:latest"; then
    echo "Building orchestrator-service Docker image..."
    cd "$ORCHESTRATOR_DIR"
    
    if [[ "$REBUILD" == "true" ]]; then
        echo "Rebuilding without cache..."
        docker build --no-cache -t opentp/orchestrator-service:latest .
    else
        docker build -t opentp/orchestrator-service:latest .
    fi
    
    if [ $? -ne 0 ]; then
        echo "Error: Failed to build orchestrator-service image"
        exit 1
    fi
    
    echo "Orchestrator service image built successfully"
    cd - > /dev/null
else
    echo "Using existing orchestrator-service image"
fi

# Deploy orchestrator service
echo "Deploying orchestrator service to Kubernetes..."
kubectl apply -f "$K8S_DIR/deployments/orchestrator.yaml"

if [ $? -ne 0 ]; then
    echo "Error: Failed to apply orchestrator Kubernetes manifests"
    exit 1
fi

echo "Waiting for orchestrator deployment to be ready..."
kubectl rollout status deployment/orchestrator-service --timeout=300s

if [ $? -eq 0 ]; then
    echo "Orchestrator service deployed successfully!"
    echo ""
    echo "Status:"
    kubectl get pods -l app=orchestrator-service
    kubectl get svc orchestrator-service
    echo ""
    echo "Checking orchestrator logs (last 10 lines):"
    kubectl logs -l app=orchestrator-service --tail=10
    echo ""
    echo "API endpoints (use 'kubectl port-forward svc/orchestrator-service 8080:8080' to access locally):"
    echo "  Health: http://localhost:8080/health"
    echo "  Status: http://localhost:8080/status" 
    echo "  Exchanges: http://localhost:8080/exchanges"
    echo ""
    echo "The orchestrator will now automatically:"
    echo "  - Start exchange pods 5 minutes before market open"
    echo "  - Stop exchange pods 5 minutes after market close"
    echo "  - Health check running exchanges every minute"
else
    echo "Error: Orchestrator deployment failed"
    echo "Check logs with: kubectl logs -l app=orchestrator-service"
    exit 1
fi

echo "Orchestrator service setup completed successfully"