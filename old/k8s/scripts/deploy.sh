#!/bin/bash

usage() { 
    echo "Usage: $0 [-n <namespace>] [-r <registry>] [-t <tag>] [-c <component>]" 
    echo "  -n: Kubernetes namespace (default: default)"
    echo "  -r: Docker registry (default: localhost:5000)"
    echo "  -t: Image tag (default: latest)"
    echo "  -c: Component to deploy (infrastructure|auth|frontend|all)"
    exit 1
}

NAMESPACE="default"
REGISTRY="localhost:5000"
TAG="latest"
COMPONENT="all"

while getopts ":n:r:t:c:" opt; do
    case ${opt} in
        n )
            NAMESPACE=$OPTARG
            ;;
        r )
            REGISTRY=$OPTARG
            ;;
        t )
            TAG=$OPTARG
            ;;
        c )
            COMPONENT=$OPTARG
            ;;
        \? )
            usage
            ;;
    esac
done

# Apply customized yaml with image settings
apply_with_replacements() {
    local file=$1
    sed "s|\${REGISTRY}|${REGISTRY}|g; s|\${TAG}|${TAG}|g; s|\${NAMESPACE}|${NAMESPACE}|g" $file | kubectl apply -f -
}

# Deploy infrastructure
deploy_infrastructure() {
    echo "Deploying infrastructure..."
    
    # Create namespaces
    kubectl create namespace kafka --dry-run=client -o yaml | kubectl apply -f -
    kubectl create namespace postgresql --dry-run=client -o yaml | kubectl apply -f -
    kubectl create namespace envoy --dry-run=client -o yaml | kubectl apply -f -
    
    # Apply Helm charts (assuming infrastructure setup via Helm)
    helm upgrade --install kafka-opentp bitnami/kafka \
        --namespace kafka \
        --values ../infrastructure/kafka/values.yaml \
        --wait
    
    helm upgrade --install opentp-postgresql bitnami/postgresql \
        --namespace postgresql \
        --values ../infrastructure/postgresql/values.yaml \
        --wait
    
    helm upgrade --install opentp-envoy envoyproxy/envoy \
        --namespace envoy \
        --values ../infrastructure/envoy/values.yaml \
        --wait
    
    # Apply DB init job
    apply_with_replacements ../jobs/db-init-job.yaml
}

# Deploy auth services
deploy_auth() {
    echo "Deploying auth services..."
    
    # Apply secrets
    kubectl apply -f ../config/secrets/database.yaml
    kubectl apply -f ../config/secrets/auth-jwt-secret.yaml
    
    # Apply auth service
    apply_with_replacements ../services/auth/authorization-service/configmap.yaml
    apply_with_replacements ../services/auth/authorization-service/deployment.yaml
    apply_with_replacements ../services/auth/authorization-service/service.yaml
}

# Deploy frontend services
deploy_frontend() {
    echo "Deploying frontend services..."
    
    # Apply frontend service
    apply_with_replacements ../services/frontend/deployment.yaml
    apply_with_replacements ../services/frontend/service.yaml
}

# Deploy all components
deploy_all() {
    deploy_infrastructure
    deploy_auth
    deploy_frontend
}

# Execute based on component selection
case $COMPONENT in
    "infrastructure")
        deploy_infrastructure
        ;;
    "auth")
        deploy_auth
        ;;
    "frontend")
        deploy_frontend
        ;;
    "all")
        deploy_all
        ;;
    *)
        echo "Invalid component: $COMPONENT"
        usage
        ;;
esac

echo "Deployment complete!"