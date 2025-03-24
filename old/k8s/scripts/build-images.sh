#!/bin/bash

# Script to build, tag and push Docker images for OpenTP components

usage() { 
    echo "Usage: $0 [-r <registry>] [-t <tag>] [-c <component>] [-p]" 
    echo "  -r: Docker registry (default: localhost:5000)"
    echo "  -t: Image tag (default: latest)"
    echo "  -c: Component to build (frontend|auth|connection|config|marketdata|orderentry|centraldesk|testexchange|socket|dataload|all)"
    echo "  -p: Push images to registry"
    exit 1
}

REGISTRY="localhost:5000"
TAG="latest"
COMPONENT="all"
PUSH=false

while getopts ":r:t:c:p" opt; do
    case ${opt} in
        r )
            REGISTRY=$OPTARG
            ;;
        t )
            TAG=$OPTARG
            ;;
        c )
            COMPONENT=$OPTARG
            ;;
        p )
            PUSH=true
            ;;
        \? )
            usage
            ;;
    esac
done

build_push() {
    local component=$1
    local context_dir=$2
    local image_name="${REGISTRY}/opentp-${component}:${TAG}"
    
    echo "Building ${image_name}..."
    docker rmi ${image_name}
    docker build --no-cache -t ${image_name} ${context_dir}
    
    if [ "$PUSH" = true ]; then
        echo "Pushing ${image_name}..."
        docker push ${image_name}
    fi
    
    echo "${component} image built successfully."
}

case $COMPONENT in
    "frontend")
        build_push "frontend" "../../frontend"
        ;;
    "auth")
        build_push "auth" "../../interface/authorization-service"
        ;;
    "connection")
        build_push "connection" "../../interface/connection-service"
        ;;
    "config")
        build_push "config" "../../interface/client-config-service"
        ;;
    "marketdata")
        build_push "marketdata" "../../interface/market-data-service"
        ;;
    "orderentry")
        build_push "orderentry" "../../interface/order-entry-service"
        ;;
    "centraldesk")
        build_push "centraldesk" "../../interface/central-desk-service"
        ;;
    "testexchange")
        build_push "testexchange" "../../interface/test-exchange-service"
        ;;
    "socket")
        build_push "socket" "../../interface/websocket-service"
        ;;
    "dataload")
        build_push "dataload" "../../dataload"
        ;;
    "all")
        build_push "frontend" "../../frontend"
        build_push "auth" "../../interface/authorization-service"
        build_push "connection" "../../interface/connection-service"
        build_push "config" "../../interface/client-config-service"
        build_push "marketdata" "../../interface/market-data-service"
        build_push "orderentry" "../../interface/order-entry-service"
        build_push "centraldesk" "../../interface/central-desk-service"
        build_push "testexchange" "../../interface/test-exchange-service"
        build_push "socket" "../../interface/websocket-service"
        build_push "dataload" "../../dataload"
        ;;
    *)
        echo "Invalid component: $COMPONENT"
        usage
        ;;
esac

echo "Build process complete!"