#!/bin/bash

usage() { 
    echo "Usage: $0 [-n <namespace>] [-c <component>]" 
    echo "  -n: Kubernetes namespace (default: default)"
    echo "  -c: Component to clean (infrastructure|auth|frontend|all)"
    exit 1
}

NAMESPACE="default"
COMPONENT="all"

while getopts ":n:c:" opt; do
    case ${opt} in
        n )
            NAMESPACE=$OPTARG
            ;;
        c )
            COMPONENT=$OPTARG
            ;;
        \? )
            usage
            ;;
    esac
done

# Clean infrastructure
clean_infrastructure() {
    echo "Cleaning infrastructure..."
    
    # Delete DB init job
    kubectl delete job db-init-job --ignore-not-found
    
    # Uninstall Helm charts
    helm uninstall opentp-envoy -n envoy
    helm uninstall opentp-postgresql -n postgresql
    helm uninstall kafka-opentp -n kafka
    
    # Remove namespaces
    kubectl delete namespace kafka --ignore-not-found
    kubectl delete namespace postgresql --ignore-not-found
    kubectl delete namespace envoy --ignore-not-found
}

# Clean auth services
clean_auth() {
    echo "Cleaning auth services..."
    
    # Delete auth service resources
    kubectl delete -f ../services/auth/authorization-service/service.yaml --ignore-not-found
    kubectl delete -f ../services/auth/authorization-service/deployment.yaml --ignore-not-found
    kubectl delete -f ../services/auth/authorization-service/configmap.yaml --ignore-not-found
    
    # Delete secrets
    kubectl delete -f ../config/secrets/auth-jwt-secret.yaml --ignore-not-found
    kubectl delete -f ../config/secrets/database.yaml --ignore-not-found
}

# Clean frontend services
clean_frontend() {
    echo "Cleaning frontend services..."
    
    # Delete frontend service resources
    kubectl delete -f ../services/frontend/service.yaml --ignore-not-found
    kubectl delete -f ../services/frontend/deployment.yaml --ignore-not-found
}

# Clean all components
clean_all() {
    clean_frontend
    clean_auth
    clean_infrastructure
}

# Execute based on component selection
case $COMPONENT in
    "infrastructure")
        clean_infrastructure
        ;;
    "auth")
        clean_auth
        ;;
    "frontend")
        clean_frontend
        ;;
    "all")
        clean_all
        ;;
    *)
        echo "Invalid component: $COMPONENT"
        usage
        ;;
esac

echo "Cleanup complete!"