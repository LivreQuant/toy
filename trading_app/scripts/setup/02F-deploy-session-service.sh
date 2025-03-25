#!/bin/bash
echo "Deploying session manager service..."

# Apply RBAC resources first
kubectl apply -f ./k8s/deployments/session-manager-rbac.yaml

# Then deploy the service
kubectl apply -f ./k8s/deployments/session-manager.yaml

# Check status
kubectl get pods -l app=session-manager