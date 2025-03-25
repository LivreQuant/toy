#!/bin/bash

# 10-simulate-network-issues.sh
SERVICE=""
ISSUE_TYPE=""
DURATION_SECONDS=60

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --service) SERVICE="$2"; shift ;;
        --issue-type) ISSUE_TYPE="$2"; shift ;;
        --duration) DURATION_SECONDS="$2"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

if [ -z "$SERVICE" ] || [ -z "$ISSUE_TYPE" ]; then
    echo "Error: Service name and issue type are required"
    echo "Usage: $0 --service SERVICE --issue-type TYPE [--duration SECONDS]"
    echo "  Issue types: latency, packet-loss, partition"
    exit 1
fi

# Validate issue type
case "$ISSUE_TYPE" in
    latency|packet-loss|partition) ;;
    *) echo "Error: Invalid issue type: $ISSUE_TYPE. Valid types are: latency, packet-loss, partition"; exit 1 ;;
esac

declare -A deployment_names
deployment_names["auth"]="auth-service"
deployment_names["session"]="session-manager"
deployment_names["order"]="order-service"
deployment_names["exchange"]="exchange-simulator"

DEPLOYMENT_NAME=${deployment_names[$SERVICE]}

if [ -z "$DEPLOYMENT_NAME" ]; then
    echo "Error: Unknown service: $SERVICE"
    exit 1
fi

# Ensure network-chaos pod is running
NETWORK_CHAOS_EXISTS=$(kubectl get pods -l app=network-chaos --no-headers 2>/dev/null)
if [ -z "$NETWORK_CHAOS_EXISTS" ]; then
    echo "Creating network-chaos pod..."
    kubectl apply -f ./k8s/tools/network-chaos.yaml
    sleep 10
fi

# Get the pod name
POD_NAME=$(kubectl get pods -l app=$DEPLOYMENT_NAME -o jsonpath="{.items[0].metadata.name}")

if [ -z "$POD_NAME" ]; then
    echo "Error: No pods found for $DEPLOYMENT_NAME"
    exit 1
fi

# Get target pod IP
TARGET_IP=$(kubectl get pod $POD_NAME -o jsonpath="{.status.podIP}")
NETWORK_CHAOS_POD=$(kubectl get pods -l app=network-chaos -o jsonpath="{.items[0].metadata.name}")

# Apply network issue
echo "Applying $ISSUE_TYPE to pod $POD_NAME for $DURATION_SECONDS seconds..."

case "$ISSUE_TYPE" in
    "latency")
        kubectl exec $NETWORK_CHAOS_POD -- tc qdisc add dev eth0 root netem delay 500ms 200ms
        ;;
    "packet-loss")
        kubectl exec $NETWORK_CHAOS_POD -- tc qdisc add dev eth0 root netem loss 20%
        ;;
    "partition")
        kubectl exec $NETWORK_CHAOS_POD -- iptables -A OUTPUT -d $TARGET_IP -j DROP
        ;;
esac

# Wait for the specified duration
echo "Network issue applied. Waiting for $DURATION_SECONDS seconds..."
for (( i=$DURATION_SECONDS; i>0; i-- )); do
    echo -ne "Time remaining: $i seconds\r"
    sleep 1
done
echo -e "\nTime's up!"

# Remove the network issue
echo "Removing network issue..."
case "$ISSUE_TYPE" in
    "latency"|"packet-loss")
        kubectl exec $NETWORK_CHAOS_POD -- tc qdisc del dev eth0 root
        ;;
    "partition")
        kubectl exec $NETWORK_CHAOS_POD -- iptables -D OUTPUT -d $TARGET_IP -j DROP
        ;;
esac

echo "Network issue removed. Normal traffic should resume."