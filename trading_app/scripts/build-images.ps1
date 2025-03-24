# scripts/build-images.ps1
param (
    [Parameter(Mandatory=$false)]
    [string[]]$Services = @("auth", "session", "order", "exchange")
)

# Point to Minikube's Docker daemon
Write-Output "Setting up Docker environment to use Minikube's Docker daemon..."
minikube docker-env | Invoke-Expression

# Define service paths and image names
$serviceConfig = @{
    "auth" = @{
        "path" = "./interface/authorization-service",
        "image" = "opentp/auth-service:latest"
    },
    "session" = @{
        "path" = "./interface/session-manager-service",
        "image" = "opentp/session-manager:latest"
    },
    "order" = @{
        "path" = "./interface/order-service",
        "image" = "opentp/order-service:latest"
    },
    "exchange" = @{
        "path" = "./interface/exchange-manager-service",
        "image" = "opentp/exchange-simulator:latest"
    }
}

# Build selected services
foreach ($service in $Services) {
    if (-not $serviceConfig.ContainsKey($service)) {
        Write-Warning "Unknown service: $service. Skipping."
        continue
    }
    
    $config = $serviceConfig[$service]
    $path = $config["path"]
    $image = $config["image"]
    
    Write-Output "Building $image from $path"
    docker build -t $image $path
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to build $image"
        exit 1
    }
    
    Write-Output "$image built successfully"
}

Write-Output "All images built successfully!"