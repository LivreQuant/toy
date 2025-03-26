#!/bin/bash
SECTION=$1

if [ -z "$SECTION" ]; then
    echo "Usage: $0 <section>"
    echo "Sections: storage databases pgbouncer db-init auth session order jaeger ingress all"
    exit 1
fi

case $SECTION in
    storage)
        echo "Resetting storage..."
        kubectl delete pvc postgres-pvc
        kubectl delete pv postgres-pv
        ;;
    databases)
        echo "Resetting database services..."
        kubectl delete service postgres redis
        kubectl delete deployment postgres redis
        ;;
    pgbouncer)
        echo "Resetting pgbouncer..."
        kubectl delete service pgbouncer
        kubectl delete deployment pgbouncer
        ;;
    db-init)
        echo "Resetting database initialization..."
        kubectl delete job db-init-job
        kubectl delete configmap db-schemas db-data
        ;;
    auth)
        echo "Resetting auth service..."
        kubectl delete service auth-service
        kubectl delete deployment auth-service
        ;;
    session)
        echo "Resetting session service..."
        kubectl delete service session-manager
        kubectl delete deployment session-manager
        kubectl delete serviceaccount session-service-account
        kubectl delete role session-service-role
        kubectl delete rolebinding session-service-role-binding
        ;;
    order)
        echo "Resetting order service..."
        kubectl delete service order-service
        kubectl delete deployment order-service
        ;;
    jaeger)
        echo "Resetting Jaeger..."
        kubectl delete service jaeger-query jaeger-collector jaeger-agent
        kubectl delete deployment jaeger
        kubectl delete configmap opentelemetry-config --ignore-not-found=true
        ;;
    ingress)
        echo "Resetting ingress..."
        kubectl delete ingress trading-platform-ingress
        ;;
    all)
        echo "Resetting everything..."
        kubectl delete ingress --all
        kubectl delete deployment --all
        kubectl delete service --all --ignore-not-found=true
        kubectl delete configmap db-schemas db-data opentelemetry-config --ignore-not-found=true
        kubectl delete job --all
        kubectl delete pvc --all
        kubectl delete pv --all
        kubectl delete serviceaccount session-service-account --ignore-not-found=true
        kubectl delete role session-service-role --ignore-not-found=true
        kubectl delete rolebinding session-service-role-binding --ignore-not-found=true
        ;;
    *)
        echo "Unknown section: $SECTION"
        exit 1
        ;;
esac

echo "Reset complete for $SECTION"