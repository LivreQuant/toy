# Scripts for Kubernetes Management

This directory contains PowerShell scripts for managing the trading platform's Kubernetes environment. These scripts automate common tasks for setup, deployment, development, and troubleshooting.

## Core Scripts

| Script | Purpose | Command |
|--------|---------|---------|
| **01-setup-local-env.ps1** | Initializes the Minikube environment, creates namespaces, and generates secrets | `.\scripts\01-setup-local-env.ps1` |
| **02-build-images.ps1** | Builds Docker images for all services | `.\scripts\02-build-images.ps1` |
| **03-deploy-services.ps1** | Deploys all services to the Kubernetes cluster | `.\scripts\03-deploy-services.ps1` |
| **06-reset-service.ps1** | Rebuilds and redeploys a specific service | `.\scripts\06-reset-service.ps1 -Service auth` |
| **07-reset-minikube.ps1** | Resets or completely rebuilds the Minikube environment | `.\scripts\07-reset-minikube.ps1 -KeepData` |
| **08-apply-all-configs.ps1** | Applies all configuration updates to the cluster | `.\scripts\08-apply-all-configs.ps1` |
| **09-circuit-breaker.ps1** | Tests circuit breaker functionality by isolating a service | `.\scripts\09-circuit-breaker.ps1 -Service auth -DurationSeconds 30` |
| **setup-all.ps1** | All-in-one setup script that runs steps 1-3 | `.\scripts\setup-all.ps1` |

## Utility Scripts

| Script | Purpose | Command |
|--------|---------|---------|
| **debug-commands.ps1** | Loads helpful debug functions | `. .\scripts\debug-commands.ps1` |
| **10-simulate-network-issues.ps1** | Simulates network problems to test resilience | `.\scripts\10-simulate-network-issues.ps1 -Service session -IssueType latency` |

## Quick Reference Guide

### Initial Setup

```powershell
# Complete one-step setup
.\scripts\setup-all.ps1

# OR step-by-step setup
.\scripts\01-setup-local-env.ps1
.\scripts\02-build-images.ps1
.\scripts\03-deploy-services.ps1
```

### Development Workflow

```powershell
# Update and restart a specific service
.\scripts\06-reset-service.ps1 -Service auth

# Apply configuration changes
.\scripts\08-apply-all-configs.ps1
```

### Debugging

```powershell
# Load debugging commands
. .\scripts\debug-commands.ps1

# Use debugging functions
Check-Pods
Get-PodLogs -PodName auth-service-xyz123
Enter-Pod -PodName auth-service-xyz123
```

### Testing Resilience

```powershell
# Test circuit breaker
.\scripts\09-circuit-breaker.ps1 -Service auth -DurationSeconds 30

# Simulate network issues
.\scripts\10-simulate-network-issues.ps1 -Service session -IssueType latency -DurationSeconds 30
```

### Shutdown and Cleanup

```powershell
# Temporarily stop Minikube
minikube stop

# Reset services but keep data
.\scripts\07-reset-minikube.ps1 -KeepData

# Complete reset (deletes all data)
.\scripts\07-reset-minikube.ps1 -Full

# Delete Minikube entirely
minikube delete
```

## Notes for Exchange Simulator

For the exchange simulator service, which is dynamically managed by the session-manager:

```powershell
# Only rebuild the exchange simulator image (doesn't deploy)
.\scripts\06-reset-service.ps1 -Service exchange

# Then restart the session-manager to pick up changes
kubectl rollout restart deployment session-manager
```

## Minikube Commands

```powershell
# Start Minikube
minikube start --driver=docker --cpus=4 --memory=8g --disk-size=20g

# Get Minikube IP
minikube ip

# Open Minikube dashboard
minikube dashboard

# Stop Minikube
minikube stop
```

## Tips

1. After starting Minikube, add its IP to your hosts file:
   ```
   <minikube-ip> trading.local
   ```

2. When developing multiple services, rebuild only the ones you're working on:
   ```powershell
   .\scripts\02-build-images.ps1 -Services @("auth", "session")
   ```

3. Use the debug commands to troubleshoot:
   ```powershell
   Get-ServiceLogs -Service auth
   Check-Volumes
   Port-Forward -Service auth-service -LocalPort 8000 -ServicePort 8000
   ```

4. When using the exchange simulator, remember that instances are created on-demand by the session-manager service. You only need to rebuild the image; you don't deploy it directly.