#!/bin/bash
echo "Deploying Jaeger for distributed tracing..."

# Get the correct path to the k8s directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
K8S_DIR="$BASE_DIR/k8s"

# Apply Jaeger configuration
kubectl apply -f "$K8S_DIR/monitoring/jaeger.yaml"

# Wait for Jaeger pod to be ready
echo "Waiting for Jaeger pod to start..."
kubectl wait --for=condition=ready pod -l app=jaeger --timeout=120s

if [ $? -ne 0 ]; then
    echo "Failed to start Jaeger pod. Checking logs..."
    pod_name=$(kubectl get pods -l app=jaeger -o jsonpath="{.items[0].metadata.name}")
    kubectl logs $pod_name
    exit 1
fi

echo "Jaeger has been successfully deployed!"
echo "Access the Jaeger UI at: http://trading.local/jaeger"