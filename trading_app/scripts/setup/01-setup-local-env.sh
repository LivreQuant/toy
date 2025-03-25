#!/bin/bash

# 01-setup-local-env.sh
FORCE_RECREATE=false

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --force-recreate) FORCE_RECREATE=true ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

echo "Starting local Kubernetes environment setup..."

# Check if script is being run as root
if [ "$(id -u)" -eq 0 ]; then
    echo "Error: This script should not be run as root or with sudo"
    echo "The docker driver for minikube cannot be run with root privileges"
    echo "Please run the script as a regular user"
    exit 1
fi

# Check if Minikube is running, if not start it
minikube status >/dev/null 2>&1
MINIKUBE_STATUS=$?

if [ $MINIKUBE_STATUS -ne 0 ] || [ "$FORCE_RECREATE" = true ]; then
    if [ "$FORCE_RECREATE" = true ] && [ $MINIKUBE_STATUS -eq 0 ]; then
        echo "Force recreating Minikube cluster..."
        minikube delete
    fi
    
    echo "Starting Minikube..."
    minikube start --driver=docker --cpus=4 --memory=8g --disk-size=20g
    
    # Check if minikube started successfully
    if [ $? -ne 0 ]; then
        echo "Error: Failed to start Minikube"
        exit 1
    fi
    
    # Enable necessary addons
    echo "Enabling Minikube addons..."
    minikube addons enable ingress
    minikube addons enable metrics-server
    minikube addons enable dashboard
fi

# Create necessary directories
echo "Setting up directory structure..."
directories=(
    "k8s/deployments"
    "k8s/storage"
    "k8s/secrets"
    "k8s/jobs"
)

for dir in "${directories[@]}"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        echo "Created directory: $dir"
    fi
done

# Generate JWT secrets if they don't exist
if [ ! -f "k8s/secrets/jwt-secret.yaml" ]; then
    echo "Generating JWT secrets..."
    JWT_SECRET=$(openssl rand -base64 32)
    JWT_REFRESH_SECRET=$(openssl rand -base64 32)
    
    cat > "k8s/secrets/jwt-secret.yaml" << EOF
apiVersion: v1
kind: Secret
metadata:
  name: auth-jwt-secret
type: Opaque
stringData:
  JWT_SECRET: "$JWT_SECRET"
  JWT_REFRESH_SECRET: "$JWT_REFRESH_SECRET"
EOF
fi

# Create database secrets if they don't exist
if [ ! -f "k8s/secrets/db-credentials.yaml" ]; then
    echo "Creating database credentials..."
    cat > "k8s/secrets/db-credentials.yaml" << EOF
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
type: Opaque
stringData:
  username: opentp
  password: samaral
  connection-string: "host=postgres dbname=opentp user=opentp password=samaral"
EOF
fi

# Create namespaces
echo "Creating namespaces..."
kubectl create namespace postgresql --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace redis --dry-run=client -o yaml | kubectl apply -f -

# Apply secrets
echo "Applying secrets..."
kubectl apply -f k8s/secrets/jwt-secret.yaml
kubectl apply -f k8s/secrets/db-credentials.yaml

# Set up hosts file entry
MINIKUBE_IP=$(minikube ip)
HOSTS_FILE="/etc/hosts"
if ! grep -q "trading.local" "$HOSTS_FILE"; then
    echo "Adding trading.local to hosts file..."
    echo "Run the following command to update your hosts file:"
    echo "sudo sh -c \"echo '$MINIKUBE_IP trading.local' >> $HOSTS_FILE\""
fi

echo "Setup complete! Your local Kubernetes environment is ready."
echo "Minikube IP: $MINIKUBE_IP"
echo ""
echo "Next steps:"
echo "1. Run './scripts/setup/02-build-images.sh' to build service images"
echo "2. Run './scripts/setup/03-deploy-services.sh' to deploy all services"
echo "3. Access the application at http://trading.local"