#!/bin/bash

# debug-commands.sh - Source this file to load debugging functions

# Function to check pod status
function check_pods() {
    namespace="default"
    selector=""
    
    # Parse arguments
    while [[ "$#" -gt 0 ]]; do
        case $1 in
            --namespace) namespace="$2"; shift ;;
            --selector) selector="$2"; shift ;;
            *) echo "Unknown parameter: $1"; return 1 ;;
        esac
        shift
    done
    
    if [ -n "$selector" ]; then
        kubectl get pods -n "$namespace" -l "$selector"
    else
        kubectl get pods -n "$namespace"
    fi
}

# Function to view logs for a specific pod
function get_pod_logs() {
    local pod_name=""
    local namespace="default"
    local follow=false
    local tail=100
    
    # Parse arguments
    while [[ "$#" -gt 0 ]]; do
        case $1 in
            --pod-name) pod_name="$2"; shift ;;
            --namespace) namespace="$2"; shift ;;
            --follow) follow=true ;;
            --tail) tail="$2"; shift ;;
            *) 
                # If the first argument without a flag is provided, assume it's the pod name
                if [ -z "$pod_name" ]; then
                    pod_name="$1"
                else
                    echo "Unknown parameter: $1"; return 1
                fi
                ;;
        esac
        shift
    done
    
    if [ -z "$pod_name" ]; then
        echo "Error: Pod name is required"
        echo "Usage: get_pod_logs [--pod-name POD_NAME] [--namespace NAMESPACE] [--follow] [--tail LINES]"
        return 1
    fi
    
    if [ "$follow" = true ]; then
        kubectl logs -n "$namespace" "$pod_name" --tail="$tail" -f
    else
        kubectl logs -n "$namespace" "$pod_name" --tail="$tail"
    fi
}

# Function to execute shell in a pod
function enter_pod() {
    local pod_name=""
    local namespace="default"
    local container=""
    
    # Parse arguments
    while [[ "$#" -gt 0 ]]; do
        case $1 in
            --pod-name) pod_name="$2"; shift ;;
            --namespace) namespace="$2"; shift ;;
            --container) container="$2"; shift ;;
            *) 
                # If the first argument without a flag is provided, assume it's the pod name
                if [ -z "$pod_name" ]; then
                    pod_name="$1"
                else
                    echo "Unknown parameter: $1"; return 1
                fi
                ;;
        esac
        shift
    done
    
    if [ -z "$pod_name" ]; then
        echo "Error: Pod name is required"
        echo "Usage: enter_pod [--pod-name POD_NAME] [--namespace NAMESPACE] [--container CONTAINER]"
        return 1
    fi
    
    if [ -n "$container" ]; then
        kubectl exec -it -n "$namespace" "$pod_name" -c "$container" -- /bin/bash
    else
        kubectl exec -it -n "$namespace" "$pod_name" -- /bin/bash
    fi
}

# Function to port-forward to a service
function port_forward() {
    local service=""
    local local_port=""
    local service_port=""
    local namespace="default"
    
    # Parse arguments
    while [[ "$#" -gt 0 ]]; do
        case $1 in
            --service) service="$2"; shift ;;
            --local-port) local_port="$2"; shift ;;
            --service-port) service_port="$2"; shift ;;
            --namespace) namespace="$2"; shift ;;
            *) echo "Unknown parameter: $1"; return 1 ;;
        esac
        shift
    done
    
    if [ -z "$service" ] || [ -z "$local_port" ] || [ -z "$service_port" ]; then
        echo "Error: Service name, local port, and service port are required"
        echo "Usage: port_forward --service SERVICE --local-port PORT --service-port PORT [--namespace NAMESPACE]"
        return 1
    fi
    
    kubectl port-forward -n "$namespace" "service/$service" "$local_port:$service_port"
}

# Function to check service details
function check_service() {
    local service=""
    local namespace="default"
    
    # Parse arguments
    while [[ "$#" -gt 0 ]]; do
        case $1 in
            --service) service="$2"; shift ;;
            --namespace) namespace="$2"; shift ;;
            *) 
                # If the first argument without a flag is provided, assume it's the service name
                if [ -z "$service" ]; then
                    service="$1"
                else
                    echo "Unknown parameter: $1"; return 1
                fi
                ;;
        esac
        shift
    done
    
    if [ -z "$service" ]; then
        echo "Error: Service name is required"
        echo "Usage: check_service [--service SERVICE] [--namespace NAMESPACE]"
        return 1
    fi
    
    kubectl describe service -n "$namespace" "$service"
}

# Function to check deployment details
function check_deployment() {
    local deployment=""
    local namespace="default"
    
    # Parse arguments
    while [[ "$#" -gt 0 ]]; do
        case $1 in
            --deployment) deployment="$2"; shift ;;
            --namespace) namespace="$2"; shift ;;
            *) 
                # If the first argument without a flag is provided, assume it's the deployment name
                if [ -z "$deployment" ]; then
                    deployment="$1"
                else
                    echo "Unknown parameter: $1"; return 1
                fi
                ;;
        esac
        shift
    done
    
    if [ -z "$deployment" ]; then
        echo "Error: Deployment name is required"
        echo "Usage: check_deployment [--deployment DEPLOYMENT] [--namespace NAMESPACE]"
        return 1
    fi
    
    kubectl describe deployment -n "$namespace" "$deployment"
}

# Function to restart a deployment
function restart_deployment() {
    local deployment=""
    local namespace="default"
    
    # Parse arguments
    while [[ "$#" -gt 0 ]]; do
        case $1 in
            --deployment) deployment="$2"; shift ;;
            --namespace) namespace="$2"; shift ;;
            *) 
                # If the first argument without a flag is provided, assume it's the deployment name
                if [ -z "$deployment" ]; then
                    deployment="$1"
                else
                    echo "Unknown parameter: $1"; return 1
                fi
                ;;
        esac
        shift
    done
    
    if [ -z "$deployment" ]; then
        echo "Error: Deployment name is required"
        echo "Usage: restart_deployment [--deployment DEPLOYMENT] [--namespace NAMESPACE]"
        return 1
    fi
    
    kubectl rollout restart deployment -n "$namespace" "$deployment"
}

# Function to view Minikube dashboard
function show_dashboard() {
    minikube dashboard
}

# Function to check persistent volumes
function check_volumes() {
    kubectl get pv,pvc
}

# Function to check logs for a specific service across all pods
function get_service_logs() {
    local service=""
    local namespace="default"
    local tail=50
    
    # Parse arguments
    while [[ "$#" -gt 0 ]]; do
        case $1 in
            --service) service="$2"; shift ;;
            --namespace) namespace="$2"; shift ;;
            --tail) tail="$2"; shift ;;
            *) 
                # If the first argument without a flag is provided, assume it's the service name
                if [ -z "$service" ]; then
                    service="$1"
                else
                    echo "Unknown parameter: $1"; return 1
                fi
                ;;
        esac
        shift
    done
    
    if [ -z "$service" ]; then
        echo "Error: Service name is required"
        echo "Usage: get_service_logs [--service SERVICE] [--namespace NAMESPACE] [--tail LINES]"
        return 1
    fi
    
    pods=$(kubectl get pods -n "$namespace" -l "app=$service" -o jsonpath="{.items[*].metadata.name}")
    for pod in $pods; do
        echo "==== Logs for $pod ===="
        kubectl logs -n "$namespace" "$pod" --tail="$tail"
        echo ""
    done
}

echo "Debug functions loaded. Available commands:"
echo "- check_pods [--namespace NAMESPACE] [--selector SELECTOR]"
echo "- get_pod_logs POD_NAME [--namespace NAMESPACE] [--follow] [--tail LINES]"
echo "- enter_pod POD_NAME [--namespace NAMESPACE] [--container CONTAINER]"
echo "- port_forward --service SERVICE --local-port PORT --service-port PORT [--namespace NAMESPACE]"
echo "- check_service SERVICE [--namespace NAMESPACE]"
echo "- check_deployment DEPLOYMENT [--namespace NAMESPACE]"
echo "- restart_deployment DEPLOYMENT [--namespace NAMESPACE]"
echo "- check_volumes"
echo "- get_service_logs SERVICE [--namespace NAMESPACE] [--tail LINES]"
echo "- show_dashboard"