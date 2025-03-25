# dev-workflow.ps1

param (
    [Parameter(Mandatory=$true)]
    [string]$Service,
    
    [Parameter(Mandatory=$false)]
    [switch]$Rebuild
)

# Point to Minikube's Docker daemon
minikube docker-env | Invoke-Expression

# Service paths
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

# Check if the service is valid
if (-not $servicePaths.ContainsKey($Service)) {
    Write-Error "Unknown service: $Service. Valid services are: $($servicePaths.Keys -join ', ')"
    exit 1
}

# Rebuild the image if requested
if ($Rebuild) {
    $path = $servicePaths[$Service]
    $imageName = "opentp/$($deploymentNames[$Service]):latest"
    
    Write-Output "Building $imageName from $path"
    docker build -t $imageName $path
}

# Restart the deployment
$deploymentName = $deploymentNames[$Service]
Write-Output "Restarting deployment $deploymentName"
kubectl rollout restart deployment $deploymentName

# Watch the pod status
kubectl get pods -w