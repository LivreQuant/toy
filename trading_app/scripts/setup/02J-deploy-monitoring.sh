#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status

# Monitoring Deployment Script
echo "Deploying Monitoring Services (Prometheus and Grafana)"

# Resolve script and directory paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
K8S_DIR="$BASE_DIR/k8s"

# Check for required dependencies
command -v kubectl >/dev/null 2>&1 || {
    echo "Error: kubectl is not installed. Exiting."
    exit 1
}

# Ensure ingress is available
echo "Verifying Ingress Configuration..."
if ! kubectl get ingress trading-platform-ingress &>/dev/null; then
    echo "Ingress not found. Running ingress setup script..."
    "$SCRIPT_DIR/02I-setup-ingress.sh"
fi

# Deploy Prometheus
echo "Deploying Prometheus Monitoring..."
kubectl apply -f "$K8S_DIR/monitoring/prometheus.yaml"

# Deploy Grafana
echo "Deploying Grafana Visualization..."
kubectl apply -f "$K8S_DIR/monitoring/grafana.yaml"

# Wait for Prometheus and Grafana to be ready
echo "Waiting for Prometheus to be ready..."
kubectl wait --for=condition=ready pod -l app=prometheus --timeout=120s

echo "Waiting for Grafana to be ready..."
kubectl wait --for=condition=ready pod -l app=grafana --timeout=120s

# Deploy Authentication Service Dashboard
echo "Creating Authentication Service Dashboard..."
kubectl create configmap auth-service-dashboard \
    --from-file="$K8S_DIR/monitoring/auth-service-dashboard.json" \
    -o yaml | kubectl apply -f -

# Create label for Grafana to recognize the dashboard
kubectl label configmap auth-service-dashboard grafana_dashboard=1 --overwrite

# Optional: Add more service dashboards here in future

# Verify deployments
echo -e "\n--- Monitoring Services Status ---"
kubectl get pods -l app=prometheus
kubectl get pods -l app=grafana

# Display access information
echo -e "\nMonitoring Services Deployed Successfully!"
echo "Access Prometheus at: http://trading.local/prometheus"
echo "Access Grafana at: http://trading.local/grafana"

# Final health check
PROMETHEUS_PODS=$(kubectl get pods -l app=prometheus -o jsonpath='{.items[*].status.phase}')
GRAFANA_PODS=$(kubectl get pods -l app=grafana -o jsonpath='{.items[*].status.phase}')

if [[ "$PROMETHEUS_PODS" == *"Running"* ]] && [[ "$GRAFANA_PODS" == *"Running"* ]]; then
    echo -e "\n✅ Monitoring infrastructure is up and running!"
else
    echo -e "\n❌ Some monitoring services failed to start. Please check logs."
    exit 1
fi