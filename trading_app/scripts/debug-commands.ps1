# debug-commands.ps1

# Function to check pod status
function Check-Pods {
    kubectl get pods
}

# Function to view logs for a specific pod
function Get-PodLogs {
    param (
        [Parameter(Mandatory=$true)]
        [string]$PodName
    )
    kubectl logs $PodName
}

# Function to execute shell in a pod
function Enter-Pod {
    param (
        [Parameter(Mandatory=$true)]
        [string]$PodName
    )
    kubectl exec -it $PodName -- /bin/bash
}

# Function to port-forward to a service
function Port-Forward {
    param (
        [Parameter(Mandatory=$true)]
        [string]$Service,
        
        [Parameter(Mandatory=$true)]
        [int]$LocalPort,
        
        [Parameter(Mandatory=$true)]
        [int]$ServicePort
    )
    kubectl port-forward service/$Service $LocalPort:$ServicePort
}

# Function to check service details
function Check-Service {
    param (
        [Parameter(Mandatory=$true)]
        [string]$Service
    )
    kubectl describe service $Service
}

# Function to check deployment details
function Check-Deployment {
    param (
        [Parameter(Mandatory=$true)]
        [string]$Deployment
    )
    kubectl describe deployment $Deployment
}

# Function to restart a deployment
function Restart-Deployment {
    param (
        [Parameter(Mandatory=$true)]
        [string]$Deployment
    )
    kubectl rollout restart deployment $Deployment
}

# Function to view Minikube dashboard
function Show-Dashboard {
    minikube dashboard
}

Write-Output "Debug functions loaded. Available commands:"
Write-Output "- Check-Pods"
Write-Output "- Get-PodLogs -PodName <pod-name>"
Write-Output "- Enter-Pod -PodName <pod-name>"
Write-Output "- Port-Forward -Service <service-name> -LocalPort <port> -ServicePort <port>"
Write-Output "- Check-Service -Service <service-name>"
Write-Output "- Check-Deployment -Deployment <deployment-name>"
Write-Output "- Restart-Deployment -Deployment <deployment-name>"
Write-Output "- Show-Dashboard"