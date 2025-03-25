#!/bin/bash

# 04-dev-workflow.sh
SERVICE=""
REBUILD=false

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --service) SERVICE="$2"; shift ;;
        --rebuild) REBUILD=true ;;
        *) 
            # If the first argument without a flag is provided, assume it's the service name
            if [ -z "$SERVICE" ]; then
                SERVICE="$1"
            else
                echo "Unknown parameter: $1"; exit 1
            fi
            ;;
    esac
    shift
done

if [ -z "$SERVICE" ]; then
    echo "Error: Service name is required"
    echo "Usage: $0 --service SERVICE [--rebuild]"
    exit 1
fi

# Point to Minikube's Docker daemon
eval $(minikube docker-env)

# Service paths
declare -A service_paths
service_paths["auth"]="./interface/authorization-service"
service_paths["session"]="./interface/session-manager-service"
service_paths["order"]="./interface/order-service"
service_paths["exchange"]="./interface/exchange-manager-service"

declare -A deployment_names
deployment_names["auth"]="auth-service"
deployment_names["session"]="session-manager"
deployment_names["order"]="order-service"
deployment_names["exchange"]="exchange-simulator"

# Check if the service is valid
if [ -z "${service_paths[$SERVICE]}" ]; then
    echo "Error: Unknown service: $SERVICE. Valid services are: auth, session, order, exchange"
    exit 1
fi

# Rebuild the image if requested
if [ "$REBUILD" = true ]; then
    path=${service_paths[$SERVICE]}
    image_name="opentp/${deployment_names[$SERVICE]}:latest"
    
    echo "Building $image_name from $path"
    docker build -t $image_name $path
fi

# Restart the deployment
deployment_name=${deployment_names[$SERVICE]}
echo "Restarting deployment $deployment_name"
kubectl rollout restart deployment $deployment_name

# Watch the pod status
kubectl get pods -w