#!/bin/bash

usage() { 
    echo "Usage: $0 [-n <namespace>] [-r <docker repo>] [-c <component>]" 
    echo "  -n: Kubernetes namespace (default: default)"
    echo "  -r: Docker repository (default: ettec)"
    echo "  -c: Component to install (auth|frontend|backend|all)"
    exit 1
}

NAMESPACE="default"
REPO="ettec"
COMPONENT="all"

while getopts ":n:r:c:" opt; do
    case ${opt} in
        n )
            NAMESPACE=$OPTARG
            ;;
        r )
            REPO=$OPTARG
            ;;
        c )
            COMPONENT=$OPTARG
            ;;
        \? )
            usage
            ;;
    esac
done

# Apply common configurations
echo "Applying common configurations..."
kubectl apply -f ../config/common/configmap.yaml

# Apply RBAC configurations
echo "Applying RBAC configurations..."
kubectl apply -f ../rbac/service-accounts/
kubectl apply -f ../rbac/roles/
kubectl apply -f ../rbac/roles/bindings/

# Apply secrets
echo "Applying secrets..."
if [ ! -f "../config/secrets/database.yaml" ]; then
    echo "Database secret not found. Creating from template..."
    cat ../config/secrets/database.template.yaml | sed "s/REPLACE_ME/password/g" > ../config/secrets/database.yaml
fi

if [ ! -f "../config/secrets/auth-jwt-secret.yaml" ]; then
    echo "JWT secret not found. Creating from template..."
    JWT_SECRET=$(openssl rand -hex 32)
    cat ../config/secrets/auth-jwt-secret.template.yaml | sed "s/REPLACE_ME_WITH_STRONG_SECRET_KEY/$JWT_SECRET/g" > ../config/secrets/auth-jwt-secret.yaml
fi

kubectl apply -f ../config/secrets/database.yaml
kubectl apply -f ../config/secrets/auth-jwt-secret.yaml

install_component() {
    local component=$1
    echo "Installing $component services..."
    kubectl apply -f ../services/$component/
}

case $COMPONENT in
    "auth")
        install_component "auth"
        ;;
    "frontend")
        install_component "frontend"
        ;;
    "backend")
        install_component "backend"
        ;;
    "all")
        install_component "auth"
        install_component "frontend"
        install_component "backend"
        ;;
    *)
        echo "Invalid component: $COMPONENT"
        usage
        ;;
esac

echo "Service installation complete!"