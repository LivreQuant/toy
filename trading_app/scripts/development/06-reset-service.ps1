# 06-reset-service.ps1
param (
    [Parameter(Mandatory=$true)]
    [string]$Service
)

# Point to Minikube's Docker daemon
minikube docker-env | Invoke-Expression

# Define service paths and deployment names
$servicePaths = @{
    "auth" = "./backend/authorization-service"
    "session" = "./backend/session-service"
    "order" = "./backend/order-service"
    "exchange" = "./backend/exchange-service"  # Keep for image building only
}

$deploymentNames = @{
    "auth" = "auth-service"
    "session" = "session-manager"
    "order" = "order-service"
    # exchange-simulator is not included as it's managed by session-service
}

$imageNames = @{
    "auth" = "opentp/auth-service:latest"
    "session" = "opentp/session-manager:latest"
    "order" = "opentp/order-service:latest"
    "exchange" = "opentp/exchange-simulator:latest"  # Keep for image building only
}

# Validate service name
if (-not $servicePaths.ContainsKey($Service)) {
    Write-Error "Unknown service: $Service. Valid services are: $($servicePaths.Keys -join ', ')"
    exit 1
}

$path = $servicePaths[$Service]
$imageName = $imageNames[$Service]

# Special handling for exchange service
if ($Service -eq "exchange") {
    Write-Output "Exchange service is managed by session-service. Only rebuilding the image..."
    
    # Remove old Docker image
    Write-Output "Removing Docker image $imageName..."
    docker rmi $imageName -f
    
    # Build new image
    Write-Output "Building new Docker image from $path..."
    docker build -t $imageName $path
    
    Write-Output "Exchange simulator image rebuilt. You may need to restart session-service to pick up changes."
    Write-Output "Run: kubectl rollout restart deployment session-manager"
    exit 0
}

$deploymentName = $deploymentNames[$Service]

# 1. Delete the current deployment
Write-Output "Deleting deployment $deploymentName..."
kubectl delete deployment $deploymentName

# 2. Remove old Docker image
Write-Output "Removing Docker image $imageName..."
docker rmi $imageName -f

# 3. Build new image
Write-Output "Building new Docker image from $path..."
docker build -t $imageName $path

# 4. Redeploy service
Write-Output "Redeploying $deploymentName..."
kubectl apply -f ./k8s/deployments/$deploymentName.yaml

# 5. Show deployment status
Write-Output "Deployment status:"
kubectl get pods -l app=$deploymentName -w