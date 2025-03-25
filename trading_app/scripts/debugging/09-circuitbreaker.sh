#!/bin/bash

# 09-circuit-breaker.sh
SERVICE=""
DURATION_SECONDS=30

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --service) SERVICE="$2"; shift ;;
        --duration) DURATION_SECONDS="$2"; shift ;;
        *) 
            # If the first argument without a flag is provided, assume it's the service name
            if [ -z "$SERVICE" ]; then
                SERVICE="$1"
            else
                echo "Unknown parameter: $1"; exit 1
            fi
            ;;
    esac
    shift
done

if [ -z "$SERVICE" ]; then
    echo "Error: Service name is required"
    echo "Usage: $0 --service SERVICE [--duration SECONDS]"
    exit 1
fi

declare -A deployment_names
deployment_names["auth"]="auth-service"
deployment_names["session"]="session-manager"
deployment_names["order"]="order-service"
deployment_names["exchange"]="exchange-simulator"

if [ -z "${deployment_names[$SERVICE]}" ]; then
    echo "Error: Unknown service: $SERVICE. Valid services are: auth, session, order, exchange"
    exit 1
fi

DEPLOYMENT_NAME=${deployment_names[$SERVICE]}

echo "Testing circuit breaker for $DEPLOYMENT_NAME for $DURATION_SECONDS seconds..."

# Create the network policy to block traffic
cat > /tmp/circuit-breaker-policy.yaml << EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: circuit-breaker-test
spec:
  podSelector:
    matchLabels:
      app: $DEPLOYMENT_NAME
  policyTypes:
  - Ingress
  - Egress
EOF

echo "Applying network policy to isolate $DEPLOYMENT_NAME..."
kubectl apply -f /tmp/circuit-breaker-policy.yaml

echo "Service is isolated. Circuit breakers should activate after multiple retries."
echo "Waiting for $DURATION_SECONDS seconds..."

# Show countdown
for (( i=$DURATION_SECONDS; i>0; i-- )); do
    echo -ne "Time remaining: $i seconds\r"
    sleep 1
done
echo -e "\nTime's up!"

# Remove the network policy
echo "Removing network policy..."
kubectl delete networkpolicy circuit-breaker-test

echo "Circuit breaker test complete. Service communication should resume."
echo "Note: Depending on your circuit breaker implementation, services may need time to recover."