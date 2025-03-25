#!/bin/bash
echo "Deploying order service..."

# Fix the initContainers issue in order-service.yaml first!
# Create a temporary fixed file
sed 's/initContainers:/spec:\n        initContainers:/' ./k8s/deployments/order-service.yaml > /tmp/fixed-order-service.yaml

# Apply the fixed file
kubectl apply -f /tmp/fixed-order-service.yaml

# Check status
kubectl get pods -l app=order-service