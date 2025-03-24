# reset-service.ps1
param (
    [Parameter(Mandatory=$true)]
    [string]$Service
)

# Point to Minikube's Docker daemon
minikube docker-env | Invoke-Expression

# Define service paths and deployment names
$servicePaths = @{
    "auth" = "./interface/authorization-service"
    "session" = "./interface/session-manager-service"
    "order" = "./interface/order-service"
    "exchange" = "./interface/exchange-manager-service"
}

$deploymentNames = @{
    "auth" = "auth-service"
    "session" = "session-manager"
    "order" = "order-service"
    "exchange" = "exchange-simulator"
}

$imageNames = @{
    "auth" = "opentp/auth-service:latest"
    "session" = "opentp/session-manager:latest"
    "order" = "opentp/order-service:latest"
    "exchange" = "opentp/exchange-simulator:latest"
}

# Validate service name
if (-not $servicePaths.ContainsKey($Service)) {
    Write-Error "Unknown service: $Service. Valid services are: $($servicePaths.Keys -join ', ')"
    exit 1
}

$path = $servicePaths[$Service]
$deploymentName = $deploymentNames[$Service]
$imageName = $imageNames[$Service]

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