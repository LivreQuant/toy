#!/bin/bash

# 03-deploy-services.sh
SKIP_BUILD=false
SKIP_INFRASTRUCTURE=false

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --skip-build) SKIP_BUILD=true ;;
        --skip-infrastructure) SKIP_INFRASTRUCTURE=true ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

echo "Deploying services to Minikube..."

# Point to Minikube's Docker daemon
eval $(minikube docker-env)

# Build images if not skipped
if [ "$SKIP_BUILD" = false ]; then
    echo "Building service images..."
    ./scripts/02-build-images.sh
fi

# Deploy infrastructure if not skipped
if [ "$SKIP_INFRASTRUCTURE" = false ]; then
    echo "Deploying infrastructure..."
    
    # Storage
    kubectl apply -f ./k8s/storage/storage.yaml
    
    # Secrets
    kubectl apply -f ./k8s/secrets/db-credentials.yaml
    kubectl apply -f ./k8s/secrets/jwt-secret.yaml
    
    # Infrastructure services
    kubectl apply -f ./k8s/deployments/postgres-deployment.yaml
    kubectl apply -f ./k8s/deployments/redis-deployment.yaml
    kubectl apply -f ./k8s/deployments/pgbouncer.yaml
    
    # Wait for postgres to be ready
    echo "Waiting for PostgreSQL to be ready..."
    ready=false
    attempts=0
    max_attempts=30
    
    while [ "$ready" = false ] && [ $attempts -lt $max_attempts ]; do
        ((attempts++))
        status=$(kubectl get pods -l app=postgres -o jsonpath="{.items[0].status.phase}")
        
        if [ "$status" = "Running" ]; then
            # Now check if it's actually ready to accept connections
            pod_name=$(kubectl get pods -l app=postgres -o jsonpath="{.items[0].metadata.name}")
            if kubectl exec -it "$pod_name" -- pg_isready -h localhost > /dev/null 2>&1; then
                ready=true
            else
                sleep 2
            fi
        else
            sleep 2
        fi
    done
    
    if [ "$ready" = false ]; then
        echo "Warning: PostgreSQL did not become ready in the expected time. Continuing anyway..."
    else
        echo "PostgreSQL is ready."
        
        # Database initialization ConfigMaps and Job
        echo "Applying database schema and data ConfigMaps..."
        kubectl apply -f ./k8s/config/db-schemas.yaml
        kubectl apply -f ./k8s/config/db-data.yaml
        
        # Initialize database
        kubectl apply -f ./k8s/jobs/db-init-job.yaml
        
        # Wait for DB init job to complete
        echo "Waiting for database initialization job to complete..."
        kubectl wait --for=condition=complete job/db-init-job --timeout=60s
    fi
fi

# Deploy application services (excluding exchange service which is managed by session-service)
echo "Deploying application services..."
kubectl apply -f ./k8s/deployments/auth-service.yaml
kubectl apply -f ./k8s/deployments/session-manager-rbac.yaml
kubectl apply -f ./k8s/deployments/session-manager.yaml
kubectl apply -f ./k8s/deployments/order-service.yaml

# Deploy ingress
kubectl apply -f ./k8s/ingress.yaml

# Show pod status
echo "All services deployed. Pod status:"
kubectl get pods

# Show ingress status
echo "Ingress status:"
kubectl get ingress

# Remind about hosts file
MINIKUBE_IP=$(minikube ip)
echo -e "\nImportant: Add the following to your hosts file (/etc/hosts):"
echo "$MINIKUBE_IP trading.local"