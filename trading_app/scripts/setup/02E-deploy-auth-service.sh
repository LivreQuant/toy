#!/bin/bash
echo "Deploying authentication service..."

# Fix the initContainers issue in auth-service.yaml first!
# Create a temporary fixed file
sed 's/initContainers:/spec:\n        initContainers:/' ./k8s/deployments/auth-service.yaml > /tmp/fixed-auth-service.yaml

# Apply the fixed file
kubectl apply -f /tmp/fixed-auth-service.yaml

# Check status
kubectl get pods -l app=auth-service