# 07-reset-minikube.ps1
param (
    [switch]$KeepData,
    [switch]$Full
)

Write-Output "Resetting Minikube environment..."

if ($Full) {
    # Full reset - stops and deletes the entire Minikube cluster
    Write-Output "Performing FULL reset - this will delete your entire cluster!"
    minikube stop
    minikube delete
    
    # Start fresh
    minikube start --driver=docker --cpus=4 --memory=8g --disk-size=20g
    minikube addons enable ingress
    minikube addons enable metrics-server
    
    # Re-run initial setup
    .\scripts\01-setup-local-env.ps1
    
    # Build all images
    .\scripts\02-build-images.ps1
    
    # Deploy everything
    .\scripts\03-deploy-services.ps1
} else {
    # Point to Minikube's Docker daemon
    minikube docker-env | Invoke-Expression
    
    if (-not $KeepData) {
        # Delete and recreate deployments, but keep database volumes
        Write-Output "Deleting deployments but preserving data..."
        
        # Delete deployments but keep PVCs
        kubectl delete deployment auth-service session-manager order-service exchange-simulator
        
        # Optionally reset the database
        Write-Output "Do you want to reset the database? (y/n)"
        $resetDB = Read-Host
        
        if ($resetDB -eq "y") {
            kubectl delete deployment postgres
            kubectl apply -f ./k8s/deployments/postgres-deployment.yaml
            # Wait for PostgreSQL to be ready
            Start-Sleep -Seconds 10
            kubectl apply -f ./k8s/jobs/db-init-job.yaml
        }
        
        # Rebuild and redeploy services
        .\scripts\02-build-images.ps1
        kubectl apply -f ./k8s/deployments/auth-service.yaml
        kubectl apply -f ./k8s/deployments/session-manager.yaml
        kubectl apply -f ./k8s/deployments/order-service.yaml
        kubectl apply -f ./k8s/deployments/exchange-simulator.yaml
    } else {
        # Just restart deployments without rebuilding
        Write-Output "Restarting all deployments..."
        kubectl rollout restart deployment auth-service session-manager order-service exchange-simulator
    }
}

# Show pod status
Write-Output "Current pod status:"
kubectl get pods