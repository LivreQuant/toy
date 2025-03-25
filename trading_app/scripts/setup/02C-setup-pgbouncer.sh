#!/bin/bash
echo "Setting up connection pooling..."

# Deploy pgbouncer after the database is ready
kubectl apply -f ./k8s/deployments/pgbouncer.yaml

# Wait for pgbouncer to be ready
echo "Waiting for pgbouncer to be ready..."
kubectl wait --for=condition=ready pod -l app=pgbouncer --timeout=60s

# Check the status
kubectl get pods -l app=pgbouncer