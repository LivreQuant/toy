# 01-setup-local-env.ps1
param (
    [switch]$ForceRecreate
)

Write-Output "Starting local Kubernetes environment setup..."

# Check if Minikube is running, if not start it
$minikubeStatus = minikube status
if ($LASTEXITCODE -ne 0 -or $ForceRecreate) {
    if ($ForceRecreate -and (minikube status)) {
        Write-Output "Force recreating Minikube cluster..."
        minikube delete
    }
    
    Write-Output "Starting Minikube..."
    minikube start --driver=docker --cpus=4 --memory=8g --disk-size=20g
    
    # Enable necessary addons
    Write-Output "Enabling Minikube addons..."
    minikube addons enable ingress
    minikube addons enable metrics-server
    minikube addons enable dashboard
}

# Create namespaces
Write-Output "Creating namespaces..."
kubectl create namespace postgresql --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace redis --dry-run=client -o yaml | kubectl apply -f -

# Create necessary directories
Write-Output "Setting up directory structure..."
$directories = @(
    "k8s/deployments",
    "k8s/storage",
    "k8s/secrets",
    "k8s/jobs"
)

foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        Write-Output "Created directory: $dir"
    }
}

# Generate JWT secrets if they don't exist
if (-not (Test-Path "k8s/secrets/jwt-secret.yaml")) {
    Write-Output "Generating JWT secrets..."
    $jwtSecret = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes([System.Guid]::NewGuid().ToString()))
    $jwtRefreshSecret = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes([System.Guid]::NewGuid().ToString()))
    
    @"
apiVersion: v1
kind: Secret
metadata:
  name: auth-jwt-secret
type: Opaque
stringData:
  JWT_SECRET: "$jwtSecret"
  JWT_REFRESH_SECRET: "$jwtRefreshSecret"
"@ | Out-File -FilePath "k8s/secrets/jwt-secret.yaml" -Encoding utf8
}

# Create database secrets if they don't exist
if (-not (Test-Path "k8s/secrets/db-credentials.yaml")) {
    Write-Output "Creating database credentials..."
    @"
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
type: Opaque
stringData:
  username: opentp
  password: samaral
  connection-string: "host=postgres dbname=opentp user=opentp password=samaral"
"@ | Out-File -FilePath "k8s/secrets/db-credentials.yaml" -Encoding utf8
}

# Apply secrets
Write-Output "Applying secrets..."
kubectl apply -f k8s/secrets/jwt-secret.yaml
kubectl apply -f k8s/secrets/db-credentials.yaml

# Set up hosts file entry
$minikubeIp = minikube ip
$hostsFile = "$env:windir\System32\drivers\etc\hosts"
$hostsContent = Get-Content $hostsFile

if (-not ($hostsContent -match "trading.local")) {
    Write-Output "Adding trading.local to hosts file..."
    Write-Output "You may need to provide administrator permission."
    
    try {
        Add-Content -Path $hostsFile -Value "`n$minikubeIp trading.local" -ErrorAction Stop
        Write-Output "Successfully added trading.local to hosts file."
    }
    catch {
        Write-Warning "Could not update hosts file automatically. Please add the following line manually to $hostsFile:"
        Write-Output "$minikubeIp trading.local"
    }
}

Write-Output "Setup complete! Your local Kubernetes environment is ready."
Write-Output "Minikube IP: $minikubeIp"
Write-Output ""
Write-Output "Next steps:"
Write-Output "1. Run '02-build-images.ps1' to build service images"
Write-Output "2. Run '03-deploy-services.ps1' to deploy all services"
Write-Output "3. Access the application at http://trading.local"