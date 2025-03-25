#!/bin/bash
echo "Deploying order service..."

# Get the correct path to the k8s directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
K8S_DIR="$BASE_DIR/k8s"

# Apply the file
kubectl apply -f "$K8S_DIR/deployments/order-service.yaml"

# Check status
echo "Waiting for order-service pods to start..."
kubectl get pods -l app=order-service -w