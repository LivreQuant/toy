#!/bin/bash
echo "Setting up ingress..."

# Fix the ingress configuration issue
# 1. Remove the configuration-snippet annotation
# 2. Fix the path type issue with /minio/?(.*) 

# Create a temporary fixed file
sed -e '/configuration-snippet/,/}/d' \
    -e 's|pathType: Prefix|pathType: ImplementationSpecific|' \
    ./k8s/ingress.yaml > /tmp/fixed-ingress.yaml

# Apply the fixed file
kubectl apply -f /tmp/fixed-ingress.yaml

# Check status
kubectl get ingress