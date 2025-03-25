# setup-all.ps1
# All-in-one setup script for the trading platform

Write-Output "Starting complete setup of trading platform in Kubernetes..."

########################################################
# docker ps -a | grep minikube
# If no container is shown, Minikube's state is inconsistent. Force delete the Minikube profile:
# minikube delete --force
# If that doesn't work, try clearing the Minikube configuration:
# minikube delete --all --purge
########################################################

# Check if Minikube is running
$minikubeStatus = minikube status
if ($LASTEXITCODE -ne 0) {
    Write-Output "Starting Minikube..."
    minikube start --driver=docker --cpus=3 --memory=4g --disk-size=20g
    minikube addons enable ingress
    minikube addons enable metrics-server
}

# Run each setup step in sequence
Write-Output "Step 1: Initialize local environment..."
.\scripts\01-setup-local-env.ps1

Write-Output "Step 2: Building Docker images..."
.\scripts\02-build-images.ps1

Write-Output "Step 3: Deploying services..."
.\scripts\03-deploy-services.ps1

# Get Minikube IP
$minikubeIp = minikube ip

Write-Output "`n====================================="
Write-Output "Setup complete! Your local Kubernetes environment is ready."
Write-Output "Access your application at http://trading.local"
Write-Output "`nMake sure you have the following entry in your hosts file:"
Write-Output "$minikubeIp trading.local"
Write-Output "`nDefault test user credentials:"
Write-Output "  Username: testuser"
Write-Output "  Password: password123"
Write-Output "====================================="