#!/bin/bash

# 06-reset-service.sh
if [ $# -lt 1 ]; then
    echo "Usage: $0 <service-name>"
    echo "  service-name: auth, session, order, or exchange"
    exit 1
fi

SERVICE=$1

# Point to Minikube's Docker daemon
eval $(minikube docker-env)

# Define service paths and deployment names
declare -A service_paths
service_paths["auth"]="./backend/authorization-service"
service_paths["session"]="./backend/session-service"
service_paths["order"]="./backend/order-service"
service_paths["exchange"]="./backend/exchange-service"  # Keep for image building only

declare -A deployment_names
deployment_names["auth"]="auth-service"
deployment_names["session"]="session-manager"
deployment_names["order"]="order-service"
# exchange-simulator is not included as it's managed by session-service

declare -A image_names
image_names["auth"]="opentp/auth-service:latest"
image_names["session"]="opentp/session-manager:latest"
image_names["order"]="opentp/order-service:latest"
image_names["exchange"]="opentp/exchange-simulator:latest"  # Keep for image building only

# Validate service name
if [[ -z "${service_paths[$SERVICE]}" ]]; then
    echo "Error: Unknown service: $SERVICE. Valid services are: auth, session, order, exchange"
    exit 1
fi

path=${service_paths[$SERVICE]}
image_name=${image_names[$SERVICE]}

# Special handling for exchange service
if [ "$SERVICE" = "exchange" ]; then
    echo "Exchange service is managed by session-service. Only rebuilding the image..."
    
    # Remove old Docker image
    echo "Removing Docker image $image_name..."
    docker rmi "$image_name" -f
    
    # Build new image
    echo "Building new Docker image from $path..."
    docker build -t "$image_name" "$path"
    
    echo "Exchange simulator image rebuilt. You may need to restart session-service to pick up changes."
    echo "Run: kubectl rollout restart deployment session-manager"
    exit 0
fi

deployment_name=${deployment_names[$SERVICE]}

# 1. Delete the current deployment
echo "Deleting deployment $deployment_name..."
kubectl delete deployment "$deployment_name"

# 2. Remove old Docker image
echo "Removing Docker image $image_name..."
docker rmi "$image_name" -f

# 3. Build new image
echo "Building new Docker image from $path..."
docker build -t "$image_name" "$path"

# 4. Redeploy service
echo "Redeploying $deployment_name..."
kubectl apply -f "./k8s/deployments/$deployment_name.yaml"

# 5. Show deployment status
echo "Deployment status:"
kubectl get pods -l app="$deployment_name" -w