#!/bin/bash

# 05-hot-reload.sh
SERVICE=""

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --service) SERVICE="$2"; shift ;;
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
    echo "Usage: $0 --service SERVICE"
    exit 1
fi

declare -A service_paths
service_paths["auth"]="./interface/authorization-service"
service_paths["session"]="./interface/session-manager-service"
service_paths["order"]="./interface/order-service"
service_paths["exchange"]="./interface/exchange-manager-service"

if [ -z "${service_paths[$SERVICE]}" ]; then
    echo "Error: Unknown service: $SERVICE"
    exit 1
fi

path=${service_paths[$SERVICE]}

echo "Starting hot reload for $SERVICE. Press Ctrl+C to stop."

# Point to Minikube's Docker daemon
eval $(minikube docker-env)

# Use inotifywait to monitor file changes (need to install inotify-tools)
# Check if inotify-tools is installed
if ! command -v inotifywait &> /dev/null; then
    echo "inotify-tools not found. Please install it with: sudo apt-get install inotify-tools"
    exit 1
fi

# Set up trap to handle cleanup when script is terminated
trap "echo -e '\nHot reload stopped.'; exit" INT TERM

# Start monitoring for file changes
while true; do
    inotifywait -r -e modify,create,delete,move "$path" | while read -r directory event filename; do
        # Skip files like .git, tmp files, etc.
        if [[ "$filename" =~ \.(tmp|log|bak)$ || "$directory" =~ \.git ]]; then
            continue
        fi
        
        timestamp=$(date +"%Y-%m-%d %H:%M:%S")
        echo "$timestamp - $directory$filename was $event"
        
        # Wait a bit to ensure all file writes are complete
        sleep 1
        
        # Rebuild and redeploy the service
        echo "Rebuilding service..."
        ./scripts/06-reset-service.sh "$SERVICE"
    done
done