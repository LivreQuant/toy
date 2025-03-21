#!/bin/bash

usage() { 
    echo "Usage: $0 [-n <namespace>] [-r <helm repo>]" 
    echo "  -n: Kubernetes namespace (default: default)"
    echo "  -r: Docker repository (default: ettec)"
    exit 1
}

NAMESPACE="default"
REPO="ettec"

while getopts ":n:r:" opt; do
    case ${opt} in
        n )
            NAMESPACE=$OPTARG
            ;;
        r )
            REPO=$OPTARG
            ;;
        \? )
            usage
            ;;
    esac
done

# Create namespaces
echo "Creating namespaces..."
kubectl create namespace kafka --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace postgresql --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace envoy --dry-run=client -o yaml | kubectl apply -f -

# Add Helm repositories
echo "Adding Helm repositories..."
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add envoyproxy https://helm.envoyproxy.io
helm repo update

# Install Kafka
echo "Installing Kafka..."
helm upgrade --install kafka-opentp bitnami/kafka \
    --namespace kafka \
    --values ../infrastructure/kafka/values.yaml \
    --wait

# Wait for Kafka to be ready
echo "Waiting for Kafka to be ready..."
kubectl wait --namespace kafka \
    --for=condition=ready pod \
    --selector=app.kubernetes.io/name=kafka \
    --timeout=300s

# Install PostgreSQL
echo "Installing PostgreSQL..."
helm upgrade --install opentp-postgresql bitnami/postgresql \
    --namespace postgresql \
    --values ../infrastructure/postgresql/values.yaml \
    --wait

# Install Envoy
echo "Installing Envoy..."
helm upgrade --install opentp-envoy envoyproxy/envoy \
    --namespace envoy \
    --values ../infrastructure/envoy/values.yaml \
    --wait

echo "Infrastructure installation complete!"