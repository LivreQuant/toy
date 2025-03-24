# Development Scripts

This directory contains PowerShell scripts for managing the local Kubernetes development environment.

## Available Scripts

### Setup and Deployment

- **setup-local-env.ps1**: Initialize the Minikube environment
- **build-images.ps1**: Build Docker images for all services
- **deploy-services.ps1**: Deploy all services to Minikube

### Development Workflow

- **dev-workflow.ps1**: Streamlined development workflow
- **reset-service.ps1**: Reset a specific service
- **reset-minikube.ps1**: Reset the entire Minikube environment

### Debugging

- **debug-commands.ps1**: Helpful commands for debugging

## Usage Examples

### Initial Setup

```powershell
# Start with a fresh environment
.\setup-local-env.ps1

# Build and deploy all services
.\deploy-services.ps1
Regular Development
powershellCopy# Make code changes to a service, then rebuild and redeploy just that service
.\reset-service.ps1 -Service auth

# Check the logs for the service
kubectl logs -l app=auth-service
Debugging
powershellCopy# Load debugging commands
. .\debug-commands.ps1

# Now you can use functions like:
Check-Pods
Get-PodLogs -PodName auth-service-xyz123
Port-Forward -Service auth-service -LocalPort 8000 -ServicePort 8000
Resetting the Environment
powershellCopy# Quick restart of all services
.\reset-minikube.ps1 -KeepData

# Complete rebuild of everything
.\reset-minikube.ps1
Adding New Services
To add a new service to the environment:

Create a deployment YAML file in k8s/deployments/
Add the service to the build-images.ps1 script
Add the service to the deploy-services.ps1 script
Add the service to the service maps in reset-service.ps1 and dev-workflow.ps1

Copy
This provides a comprehensive file structure and the missing files you requested. I've organized everything in a logical manner to help you easily develop, test, and manage your Kubernetes environment for the trading platform.