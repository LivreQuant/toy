#!/bin/bash

usage() { 
    echo "Usage: $0 [-n <namespace>] [-c <component>]" 
    echo "  -n: Kubernetes namespace (default: default)"
    echo "  -c: Component to uninstall (infrastructure|services|all)"
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

uninstall_infrastructure() {
    echo "Uninstalling infrastructure..."
    
    # Uninstall Envoy
    helm uninstall opentp-envoy -n envoy
    
    # Uninstall PostgreSQL
    helm uninstall opentp-postgresql -n postgresql
    
    # Uninstall Kafka
    helm uninstall kafka-opentp -n kafka
    
    # Remove namespaces
    kubectl delete namespace kafka
    kubectl delete namespace postgresql
    kubectl delete namespace envoy
}

uninstall_services() {
    echo "Uninstalling services..."
    
    # Remove services
    kubectl delete -f ../services/auth/ --ignore-not-found
    kubectl delete -f ../services/market-data/ --ignore-not-found
    kubectl delete -f ../services/order-management/ --ignore-not-found
    kubectl delete -f ../services/trading/ --ignore-not-found
    
    # Remove RBAC
    kubectl delete -f ../rbac/roles/bindings/ --ignore-not-found
    kubectl delete -f ../rbac/roles/ --ignore-not-found
    kubectl delete -f ../rbac/service-accounts/ --ignore-not-found
    
    # Remove configs
    kubectl delete -f ../config/common/configmap.yaml --ignore-not-found
}

case $COMPONENT in
    "infrastructure")
        uninstall_infrastructure
        ;;
    "services")
        uninstall_services
        ;;
    "all")
        uninstall_services
        uninstall_infrastructure
        ;;
    *)
        echo "Invalid component: $COMPONENT"
        usage
        ;;
esac

echo "Uninstallation complete!"