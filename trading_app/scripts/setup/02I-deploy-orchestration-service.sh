#!/bin/bash
# 02I-deploy-orchestration-service.sh
echo "Building and deploying orchestrator service..."

# Get the correct path to the directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
K8S_DIR="$BASE_DIR/k8s"
BACKEND_DIR="$BASE_DIR/../backend"
ORCHESTRATOR_DIR="$BACKEND_DIR/orchestrator-service"

# Parse arguments
REBUILD=false
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --rebuild) REBUILD=true ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Verify orchestrator directory exists
if [ ! -d "$ORCHESTRATOR_DIR" ]; then
    echo "Error: Orchestrator service directory not found at: $ORCHESTRATOR_DIR"
    echo "Expected structure: backend/orchestrator-service/"
    exit 1
fi

# Verify required files exist
if [ ! -f "$ORCHESTRATOR_DIR/Dockerfile" ]; then
    echo "Error: Dockerfile not found in orchestrator service directory"
    exit 1
fi

if [ ! -f "$ORCHESTRATOR_DIR/requirements.txt" ]; then
    echo "Error: requirements.txt not found in orchestrator service directory"
    exit 1
fi

# Point to Minikube's Docker daemon
eval $(minikube docker-env)

# Build orchestrator image
if [[ "$REBUILD" == "true" ]] || ! docker images opentp/orchestrator-service:latest --format "{{.Repository}}:{{.Tag}}" | grep -q "opentp/orchestrator-service:latest"; then
    echo "Building orchestrator-service Docker image..."
    cd "$ORCHESTRATOR_DIR"
    
    # Verify we're in the right directory
    echo "Building from directory: $(pwd)"
    
    if [[ "$REBUILD" == "true" ]]; then
        echo "Rebuilding without cache..."
        docker build --no-cache -t opentp/orchestrator-service:latest .
    else
        docker build -t opentp/orchestrator-service:latest .
    fi
    
    if [ $? -ne 0 ]; then
        echo "Error: Failed to build orchestrator-service image"
        echo "Current directory: $(pwd)"
        echo "Directory contents:"
        ls -la
        exit 1
    fi
    
    echo "Orchestrator service image built successfully"
    cd - > /dev/null
else
    echo "Using existing orchestrator-service image"
fi

# Verify Kubernetes manifests exist
ORCHESTRATOR_RBAC_MANIFEST="$K8S_DIR/deployments/orchestrator-service-rbac.yaml"
ORCHESTRATOR_SERVICE_MANIFEST="$K8S_DIR/deployments/orchestrator-service.yaml"

if [ ! -f "$ORCHESTRATOR_RBAC_MANIFEST" ]; then
    echo "Error: Orchestrator RBAC manifest not found at: $ORCHESTRATOR_RBAC_MANIFEST"
    echo "Please ensure the orchestrator-service-rbac.yaml file exists in k8s/deployments/"
    exit 1
fi

if [ ! -f "$ORCHESTRATOR_SERVICE_MANIFEST" ]; then
    echo "Error: Orchestrator service manifest not found at: $ORCHESTRATOR_SERVICE_MANIFEST"
    echo "Please ensure the orchestrator-service.yaml file exists in k8s/deployments/"
    exit 1
fi

# Deploy RBAC resources first (ServiceAccount, Role, RoleBinding)
echo "Deploying orchestrator RBAC resources..."
kubectl apply -f "$ORCHESTRATOR_RBAC_MANIFEST"

if [ $? -ne 0 ]; then
    echo "Error: Failed to apply orchestrator RBAC manifests"
    exit 1
fi

echo "RBAC resources deployed successfully"

# Deploy orchestrator service
echo "Deploying orchestrator service to Kubernetes..."
kubectl apply -f "$ORCHESTRATOR_SERVICE_MANIFEST"

if [ $? -ne 0 ]; then
    echo "Error: Failed to apply orchestrator service manifests"
    exit 1
fi

echo "Waiting for orchestrator deployment to be ready..."
kubectl rollout status deployment/orchestrator-service --timeout=300s

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Orchestrator service deployed successfully!"
    echo ""
    echo "📊 Status:"
    kubectl get pods -l app=orchestrator-service
    kubectl get svc orchestrator-service
    echo ""
    echo "🔍 RBAC Resources:"
    kubectl get serviceaccount orchestrator-service-account
    kubectl get role orchestrator-service-role
    kubectl get rolebinding orchestrator-service-role-binding
    echo ""
    echo "📋 Recent logs (last 10 lines):"
    sleep 5  # Give the pod a moment to start logging
    kubectl logs -l app=orchestrator-service --tail=10 || echo "Logs not yet available"
    echo ""
    echo "🌐 API endpoints:"
    echo "  To access locally, run: kubectl port-forward svc/orchestrator-service 8080:8080"
    echo "  Then visit:"
    echo "    Health: http://localhost:8080/health"
    echo "    Status: http://localhost:8080/status" 
    echo "    Exchanges: http://localhost:8080/exchanges"
    echo ""
    echo "🔄 Orchestrator capabilities:"
    echo "  ✓ Start exchange pods 5 minutes before market open"
    echo "  ✓ Stop exchange pods 5 minutes after market close"
    echo "  ✓ Health check running exchanges every minute"
    echo "  ✓ Full Kubernetes API access for pod management"
    echo ""
    echo "🎯 Next steps:"
    echo "  1. Check logs: kubectl logs -f deployment/orchestrator-service"
    echo "  2. Verify database connection and exchange metadata"
    echo "  3. Test manual exchange start/stop via API"
    
else
    echo ""
    echo "❌ Orchestrator deployment failed"
    echo ""
    echo "🔍 Troubleshooting information:"
    echo "  Check deployment status: kubectl describe deployment orchestrator-service"
    echo "  Check pod status: kubectl get pods -l app=orchestrator-service"
    echo "  Check pod logs: kubectl logs -l app=orchestrator-service"
    echo "  Check events: kubectl get events --sort-by=.metadata.creationTimestamp"
    exit 1
fi

echo ""
echo "🎉 Orchestrator service setup completed successfully!"