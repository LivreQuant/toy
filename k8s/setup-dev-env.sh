#!/bin/bash
# k8s/setup-dev-env.sh

# Create minikube cluster if needed
if ! minikube status > /dev/null 2>&1; then
  echo "Starting minikube..."
  minikube start --memory=4096 --cpus=2
fi

# Enable ingress
minikube addons enable ingress

# Create DB credentials
kubectl create secret generic db-credentials \
  --from-literal=username=opentp \
  --from-literal=password=samaral

# Apply PostgreSQL setup
kubectl apply -f k8s-dev/postgres.yaml

# Build and load the session manager image
eval $(minikube docker-env)
docker build -t session-manager:dev .

# Apply session manager deployment
kubectl apply -f k8s-dev/session-manager.yaml

# Setup NGINX Ingress Controller for gRPC
echo "Setting up NGINX Ingress Controller for gRPC..."
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.1.0/deploy/static/provider/cloud/deploy.yaml

# Create gRPC ingress
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: grpc-ingress
  annotations:
    kubernetes.io/ingress.class: "nginx"
    nginx.ingress.kubernetes.io/backend-protocol: "GRPC"
    nginx.ingress.kubernetes.io/ssl-redirect: "false"
    nginx.ingress.kubernetes.io/affinity: "cookie"
    nginx.ingress.kubernetes.io/session-cookie-name: "SESSIONAFFINITY"
    nginx.ingress.kubernetes.io/session-cookie-expires: "172800"
    nginx.ingress.kubernetes.io/session-cookie-max-age: "172800"
spec:
  rules:
  - host: session-api.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: session-manager
            port:
              number: 50052
EOF

# Set up hosts entry for local testing
echo "Adding hosts entry for session-api.local and auth-api.local..."
MINIKUBE_IP=$(minikube ip)
if ! grep -q "session-api.local" /etc/hosts; then
  echo "$MINIKUBE_IP session-api.local auth-api.local" | sudo tee -a /etc/hosts
fi

# Output helpful information
echo ""
echo "Development environment setup complete!"
echo "Access URLs:"
echo " - Session API: http://session-api.local"
echo " - Auth API: http://auth-api.local"
echo ""
echo "To access the frontend, run:"
echo "  npm start"
echo ""
echo "To update frontend configuration for local Kubernetes testing:"
echo "  Edit src/services/config/ServiceConfig.ts if needed"
echo ""
echo "To test connection to services:"
echo "  curl -v http://session-api.local/healthz"
echo ""