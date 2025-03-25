#!/bin/bash

# 08-apply-all-configs.sh
COMPONENTS=("deployments" "storage" "network" "ingress" "monitoring")

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --components) 
            IFS=',' read -r -a COMPONENTS <<< "$2"
            shift
            ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

echo "Applying Kubernetes configurations..."

# Point to Minikube's Docker daemon
eval $(minikube docker-env)

# Helper function to apply configurations
apply_configs() {
    local path="$1"
    
    if [ -d "$path" ]; then
        for file in "$path"/*.yaml; do
            if [ -f "$file" ]; then
                echo "Applying $file..."
                kubectl apply -f "$file"
            fi
        done
    else
        echo "Warning: Path not found: $path"
    fi
}

# Apply configurations based on selected components
for component in "${COMPONENTS[@]}"; do
    echo "Applying $component configurations..."
    
    case "$component" in
        "deployments")
            apply_configs "./k8s/deployments"
            ;;
        "storage")
            apply_configs "./k8s/storage"
            ;;
        "network")
            apply_configs "./k8s/network"
            ;;
        "ingress")
            apply_configs "./k8s/ingress"
            # If using base directory for ingress
            if [ -f "./k8s/ingress.yaml" ]; then
                kubectl apply -f "./k8s/ingress.yaml"
            fi
            ;;
        "secrets")
            apply_configs "./k8s/secrets"
            ;;
        "monitoring")
            apply_configs "./k8s/monitoring"
            ;;
        "autoscaling")
            apply_configs "./k8s/autoscaling"
            ;;
        "podpolicies")
            apply_configs "./k8s/podpolicies"
            ;;
        *)
            echo "Warning: Unknown component: $component"
            ;;
    esac
done

echo "Configuration update complete. Checking deployment status..."
kubectl get pods