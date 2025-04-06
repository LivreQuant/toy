#!/bin/bash
echo "Setting up storage resources..."

# Apply storage configurations
kubectl apply -f ../../k8s/storage/storage.yaml

# Check the created resources
kubectl get pv,pvc