# apply-all-configs.ps1

Write-Output "Applying updated Kubernetes configurations..."

# Create network policies
kubectl apply -f k8s/network/network-policy.yaml

# Apply deployments with enhanced settings
kubectl apply -f k8s/deployments/auth-service.yaml
kubectl apply -f k8s/deployments/session-manager.yaml
kubectl apply -f k8s/deployments/order-service.yaml
kubectl apply -f k8s/deployments/exchange-service.yaml
kubectl apply -f k8s/deployments/pgbouncer.yaml
kubectl apply -f k8s/deployments/redis-deployment.yaml
kubectl apply -f k8s/deployments/postgres-deployment.yaml

# Apply autoscaling configs
kubectl apply -f k8s/autoscaling/hpa.yaml

# Apply availability policies
kubectl apply -f k8s/podpolicies/pdb.yaml

# Apply updated ingress with session affinity
kubectl apply -f k8s/ingress.yaml

Write-Output "All configurations applied. Checking deployment status..."
kubectl get pods