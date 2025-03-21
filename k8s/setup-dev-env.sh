#!/bin/bash
# setup-dev-env.sh

# Create minikube cluster if needed
if ! minikube status > /dev/null 2>&1; then
  echo "Starting minikube..."
  minikube start --memory=4096 --cpus=2
fi

# Enable ingress
minikube addons enable ingress

# Create DB credentials
kubectl create secret generic db-credentials \
  --from-literal=username=opentp \
  --from-literal=password=samaral

# Apply PostgreSQL setup
kubectl apply -f k8s-dev/postgres.yaml

# Build and load the session manager image
eval $(minikube docker-env)
docker build -t session-manager:dev .

# Apply session manager deployment
kubectl apply -f k8s-dev/session-manager.yaml

# Set up hosts entry for local testing
echo "Adding hosts entry for session-api.local..."
echo "$(minikube ip) session-api.local" | sudo tee -a /etc/hosts

echo "Development environment setup complete!"