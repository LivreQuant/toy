#!/bin/bash
SECTION=$1

if [ -z "$SECTION" ]; then
    echo "Usage: $0 <section>"
    echo "Sections: storage databases pgbouncer db-init minio auth session fund orchestrator simulator exch-us-equities jaeger ingress monitor algorand all"
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
        kubectl delete service postgres
        kubectl delete deployment postgres
        ;;
    pgbouncer)
        echo "Resetting pgbouncer..."
        kubectl delete service pgbouncer
        kubectl delete deployment pgbouncer
        ;;
    db-init)
        echo "Resetting database initialization..."
        kubectl delete job db-init-job
        kubectl delete configmap db-schemas-auth db-schemas-session db-schemas-fund db-schemas-crypto
        ;;
    jaeger)
        echo "Resetting Jaeger..."
        kubectl delete service jaeger-query jaeger-collector jaeger-agent
        kubectl delete deployment jaeger
        kubectl delete configmap opentelemetry-config --ignore-not-found=true
        ;;
    minio)
        echo "Resetting Conviction..."
        kubectl delete deployment storage-service
        kubectl delete service storage-service
        kubectl delete pvc storage-pvc
        kubectl delete secret storage-credentials --ignore-not-found=true
        ;;
    auth)
        echo "Resetting auth service..."
        kubectl delete service auth-service
        kubectl delete deployment auth-service
        ;;
    session)
        echo "Resetting session service..."
        kubectl delete service session-service
        kubectl delete deployment session-service
        kubectl delete serviceaccount session-service-account
        kubectl delete role session-service-role
        kubectl delete rolebinding session-service-role-binding
        ;;
    orchestrator)
        echo "Resetting orchestrator service..."
        kubectl delete service orchestrator-service
        kubectl delete deployment orchestrator-service
        kubectl delete serviceaccount orchestrator-service-account
        kubectl delete role orchestrator-service-role
        kubectl delete rolebinding orchestrator-service-role-binding
        ;;
    fund)
        echo "Resetting fund service..."
        kubectl delete service fund-service
        kubectl delete deployment fund-service
        ;;
    simulator)
        echo "Resetting exchange service resources..."
        kubectl delete configmap exchange-service-config --ignore-not-found=true
        kubectl delete serviceaccount exchange-service-account --ignore-not-found=true
        # Clean up any running service pods (they all have service-* in their name)
        kubectl delete deployment exchange-service --ignore-not-found=true
        kubectl delete service exchange-service --ignore-not-found=true
        ;;
    exch-us-equities)
        echo "Resetting exch-us-equities market data service..."
        kubectl delete service exch-us-equities-market-data
        kubectl delete deployment exch-us-equities-market-data
        ;;
    ingress)
        echo "Resetting ingress..."
        kubectl delete ingress trading-platform-ingress
        ;;
    monitor)
        echo "Resetting monitoring services..."
        kubectl delete deployment prometheus grafana
        kubectl delete service prometheus grafana
        kubectl delete configmap prometheus-config grafana-datasources auth-service-dashboard --ignore-not-found=true
        ;;
    algorand)
        echo "Resetting algorand services..."
        kubectl delete service algorand-localnet
        # kubectl delete endpoints algorand-localnet
        ;;
    *)
        echo "Unknown section: $SECTION"
        exit 1
        ;;
esac

echo "Reset complete for $SECTION"