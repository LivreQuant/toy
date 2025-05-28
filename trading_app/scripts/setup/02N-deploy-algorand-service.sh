#!/bin/bash
echo "Deploying Algorand LocalNet external service..."

# Get the correct path to the directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
K8S_DIR="$BASE_DIR/k8s"

# Create the algorand-external-service.yaml if it doesn't exist
ALGORAND_SERVICE_FILE="$K8S_DIR/deployments/algorand-external-service.yaml"

echo "Creating algorand-external-service.yaml..."
mkdir -p "$K8S_DIR/deployments"

# Get the actual host IP that Kubernetes pods can reach
# Use the first non-loopback IP from hostname -I
HOST_IP=$(hostname -I | awk '{print $1}')

# Validate that we got an IP
if [ -z "$HOST_IP" ] || [ "$HOST_IP" = "127.0.0.1" ]; then
    echo "Warning: Could not detect proper host IP, using fallback"
    # Try alternative methods
    HOST_IP=$(ip route get 8.8.8.8 | awk -F"src " 'NR==1{split($2,a," ");print a[1]}' 2>/dev/null)
    if [ -z "$HOST_IP" ]; then
        HOST_IP="172.17.0.1"  # Final fallback
    fi
fi

echo "Using host IP: $HOST_IP"

# Test connectivity to LocalNet before creating service
echo "Testing LocalNet connectivity on $HOST_IP..."
if curl -s -m 5 "http://$HOST_IP:4001/v2/status" \
   -H "X-Algo-API-Token: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" \
   > /dev/null; then
    echo "✅ LocalNet is accessible on $HOST_IP:4001"
else
    echo "❌ Warning: LocalNet may not be accessible on $HOST_IP:4001"
    echo "   Make sure 'algokit localnet start' is running"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

cat > "$ALGORAND_SERVICE_FILE" << EOF
apiVersion: v1
kind: Service
metadata:
  name: algorand-localnet
  namespace: default
spec:
  clusterIP: None  # Headless service
  ports:
  - name: algod
    port: 4001
    protocol: TCP
  - name: indexer
    port: 8980
    protocol: TCP
---
apiVersion: v1
kind: Endpoints
metadata:
  name: algorand-localnet
  namespace: default
subsets:
- addresses:
  - ip: $HOST_IP
  ports:
  - name: algod
    port: 4001
    protocol: TCP
  - name: indexer
    port: 8980
    protocol: TCP
EOF

echo "Created $ALGORAND_SERVICE_FILE with host IP: $HOST_IP"

# Apply the service
echo "Applying Algorand LocalNet external service..."
kubectl apply -f "$ALGORAND_SERVICE_FILE"

if [ $? -eq 0 ]; then
    echo "✅ Algorand LocalNet external service deployed successfully"
    
    # Check the service status
    echo "Service details:"
    kubectl get service algorand-localnet
    kubectl get endpoints algorand-localnet
    
    echo ""
    echo "🔧 Configuration for your fund service:"
    echo "ALGOD_SERVER=http://algorand-localnet"
    echo "ALGOD_PORT=4001"
    echo "INDEXER_SERVER=http://algorand-localnet"
    echo "INDEXER_PORT=8980"
    echo ""
    echo "📝 Make sure your Algorand LocalNet is running:"
    echo "algokit localnet start"
    echo "algokit localnet status"
    
    # Auto-test the service
    echo ""
    echo "🧪 Testing service connectivity..."
    kubectl run test-connection --rm --image=curlimages/curl --restart=Never -- \
        curl -s -m 10 "http://algorand-localnet:4001/v2/status" \
        -H "X-Algo-API-Token: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" \
        > /dev/null
    
    if [ $? -eq 0 ]; then
        echo "✅ Service connectivity test passed!"
        echo ""
        echo "🚀 Ready to update your fund service:"
        echo "kubectl set env deployment/fund-service ALGOD_SERVER=http://algorand-localnet ALGOD_PORT=4001 INDEXER_SERVER=http://algorand-localnet INDEXER_PORT=8980"
    else
        echo "❌ Service connectivity test failed"
        echo "   You may need to manually configure with IP: $HOST_IP"
    fi
    
else
    echo "❌ Failed to deploy Algorand external service"
    exit 1
fi