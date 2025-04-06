#!/bin/bash
echo "Setting up connection pooling..."

# Get the correct path to the k8s directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
K8S_DIR="$BASE_DIR/k8s"

# Deploy pgbouncer after the database is ready
kubectl apply -f "$K8S_DIR/deployments/pgbouncer.yaml"

# Wait for pgbouncer to be ready
echo "Waiting for pgbouncer to be ready..."
kubectl wait --for=condition=ready pod -l app=pgbouncer --timeout=60s

# Check the status
kubectl get pods -l app=pgbouncer