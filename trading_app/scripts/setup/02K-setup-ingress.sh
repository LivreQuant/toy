#!/bin/bash
echo "Setting up ingress..."

# Get the correct path to the k8s directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
K8S_DIR="$BASE_DIR/k8s"

# Apply the ingress configuration
kubectl apply -f $K8S_DIR/ingress.yaml

# Check status
kubectl get ingress