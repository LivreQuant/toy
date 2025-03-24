# scripts/deploy-services.ps1
param (
    [switch]$SkipBuild,
    [switch]$SkipInfrastructure
)

Write-Output "Deploying services to Minikube..."

# Point to Minikube's Docker daemon
minikube docker-env | Invoke-Expression

# Build images if not skipped
if (-not $SkipBuild) {
    Write-Output "Building service images..."
    .\scripts\build-images.ps1
}

# Deploy infrastructure if not skipped
if (-not $SkipInfrastructure) {
    Write-Output "Deploying infrastructure..."
    
    # Storage
    kubectl apply -f ./k8s/storage/storage.yaml
    
    # Secrets
    kubectl apply -f ./k8s/secrets/db-credentials.yaml
    kubectl apply -f ./k8s/secrets/jwt-secret.yaml
    
    # Infrastructure services
    kubectl apply -f ./k8s/deployments/postgres-deployment.yaml
    kubectl apply -f ./k8s/deployments/redis-deployment.yaml
    kubectl apply -f ./k8s/deployments/pgbouncer.yaml
    
    # Wait for postgres to be ready
    Write-Output "Waiting for PostgreSQL to be ready..."
    $ready = $false
    $attempts = 0
    $maxAttempts = 30
    
    while (-not $ready -and $attempts -lt $maxAttempts) {
        $attempts++
        $status = kubectl get pods -l app=postgres -o jsonpath="{.items[0].status.phase}"
        
        if ($status -eq "Running") {
            # Now check if it's actually ready to accept connections
            try {
                $ready = kubectl exec -it $(kubectl get pods -l app=postgres -o jsonpath="{.items[0].metadata.name}") -- pg_isready -h localhost
                if ($LASTEXITCODE -eq 0) {
                    $ready = $true
                }
            } catch {
                Start-Sleep -Seconds 2
            }
        } else {
            Start-Sleep -Seconds 2
        }
    }
    
    if (-not $ready) {
        Write-Warning "PostgreSQL did not become ready in the expected time. Continuing anyway..."
    } else {
        Write-Output "PostgreSQL is ready."
        
        # Initialize database
        kubectl apply -f ./k8s/jobs/db-init-job.yaml
        
        # Wait for DB init job to complete
        Write-Output "Waiting for database initialization job to complete..."
        kubectl wait --for=condition=complete job/db-init-job --timeout=60s
    }
}

# Deploy application services
Write-Output "Deploying application services..."
kubectl apply -f ./k8s/deployments/auth-service.yaml
kubectl apply -f ./k8s/deployments/session-manager.yaml
kubectl apply -f ./k8s/deployments/order-service.yaml
kubectl apply -f ./k8s/deployments/exchange-simulator.yaml

# Deploy ingress
kubectl apply -f ./k8s/ingress.yaml

# Show pod status
Write-Output "All services deployed. Pod status:"
kubectl get pods

# Show ingress status
Write-Output "Ingress status:"
kubectl get ingress

# Remind about hosts file
$minikubeIp = minikube ip
Write-Output "`nImportant: Add the following to your hosts file (C:\Windows\System32\drivers\etc\hosts):"
Write-Output "$minikubeIp trading.local"