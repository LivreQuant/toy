#!/bin/bash

# setup-all.sh
# All-in-one setup script for the trading platform

echo "Starting complete setup of trading platform in Kubernetes..."

# Check if Minikube is running
minikube status
if [ $? -ne 0 ]; then
    echo "Starting Minikube..."
    minikube start --driver=docker --cpus=3 --memory=4g --disk-size=20g
    minikube addons enable ingress
    minikube addons enable metrics-server
fi

# Run each setup step in sequence
echo "Step 1: Initialize local environment..."
./scripts/01-setup-local-env.sh

echo "Step 2: Building Docker images..."
./scripts/02-build-images.sh

echo "Step 3: Deploying services..."
./scripts/03-deploy-services.sh

# Get Minikube IP
MINIKUBE_IP=$(minikube ip)

echo -e "\n====================================="
echo "Setup complete! Your local Kubernetes environment is ready."
echo "Access your application at http://trading.local"
echo -e "\nMake sure you have the following entry in your hosts file:"
echo "$MINIKUBE_IP trading.local"
echo -e "\nDefault test user credentials:"
echo "  Username: testuser"
echo "  Password: password123"
echo "====================================="