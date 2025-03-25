# debug-commands.ps1

# Function to check pod status
function Check-Pods {
    param (
        [Parameter(Mandatory=$false)]
        [string]$Namespace = "default",
        
        [Parameter(Mandatory=$false)]
        [string]$Selector = ""
    )
    
    if ($Selector) {
        kubectl get pods -n $Namespace -l $Selector
    } else {
        kubectl get pods -n $Namespace
    }
}

# Function to view logs for a specific pod
function Get-PodLogs {
    param (
        [Parameter(Mandatory=$true)]
        [string]$PodName,
        
        [Parameter(Mandatory=$false)]
        [string]$Namespace = "default",
        
        [Parameter(Mandatory=$false)]
        [switch]$Follow,
        
        [Parameter(Mandatory=$false)]
        [int]$Tail = 100
    )
    
    if ($Follow) {
        kubectl logs -n $Namespace $PodName --tail=$Tail -f
    } else {
        kubectl logs -n $Namespace $PodName --tail=$Tail
    }
}

# Function to execute shell in a pod
function Enter-Pod {
    param (
        [Parameter(Mandatory=$true)]
        [string]$PodName,
        
        [Parameter(Mandatory=$false)]
        [string]$Namespace = "default",
        
        [Parameter(Mandatory=$false)]
        [string]$Container = ""
    )
    
    if ($Container) {
        kubectl exec -it -n $Namespace $PodName -c $Container -- /bin/bash
    } else {
        kubectl exec -it -n $Namespace $PodName -- /bin/bash
    }
}

# Function to port-forward to a service
function Port-Forward {
    param (
        [Parameter(Mandatory=$true)]
        [string]$Service,
        
        [Parameter(Mandatory=$true)]
        [int]$LocalPort,
        
        [Parameter(Mandatory=$true)]
        [int]$ServicePort,
        
        [Parameter(Mandatory=$false)]
        [string]$Namespace = "default"
    )
    
    kubectl port-forward -n $Namespace service/$Service $LocalPort:$ServicePort
}

# Function to check service details
function Check-Service {
    param (
        [Parameter(Mandatory=$true)]
        [string]$Service,
        
        [Parameter(Mandatory=$false)]
        [string]$Namespace = "default"
    )
    
    kubectl describe service -n $Namespace $Service
}

# Function to check deployment details
function Check-Deployment {
    param (
        [Parameter(Mandatory=$true)]
        [string]$Deployment,
        
        [Parameter(Mandatory=$false)]
        [string]$Namespace = "default"
    )
    
    kubectl describe deployment -n $Namespace $Deployment
}

# Function to restart a deployment
function Restart-Deployment {
    param (
        [Parameter(Mandatory=$true)]
        [string]$Deployment,
        
        [Parameter(Mandatory=$false)]
        [string]$Namespace = "default"
    )
    
    kubectl rollout restart deployment -n $Namespace $Deployment
}

# Function to view Minikube dashboard
function Show-Dashboard {
    minikube dashboard
}

# Function to check persistent volumes
function Check-Volumes {
    kubectl get pv,pvc
}

# Function to check logs for a specific service across all pods
function Get-ServiceLogs {
    param (
        [Parameter(Mandatory=$true)]
        [string]$Service,
        
        [Parameter(Mandatory=$false)]
        [string]$Namespace = "default",
        
        [Parameter(Mandatory=$false)]
        [int]$Tail = 50
    )
    
    $pods = kubectl get pods -n $Namespace -l app=$Service -o jsonpath="{.items[*].metadata.name}"
    foreach ($pod in $pods.Split()) {
        Write-Output "==== Logs for $pod ===="
        kubectl logs -n $Namespace $pod --tail=$Tail
        Write-Output ""
    }
}

Write-Output "Debug functions loaded. Available commands:"
Write-Output "- Check-Pods [-Namespace <namespace>] [-Selector <label-selector>]"
Write-Output "- Get-PodLogs -PodName <pod-name> [-Namespace <namespace>] [-Follow] [-Tail <lines>]"
Write-Output "- Enter-Pod -PodName <pod-name> [-Namespace <namespace>] [-Container <container-name>]"
Write-Output "- Port-Forward -Service <service-name> -LocalPort <port> -ServicePort <port> [-Namespace <namespace>]"
Write-Output "- Check-Service -Service <service-name> [-Namespace <namespace>]"
Write-Output "- Check-Deployment -Deployment <deployment-name> [-Namespace <namespace>]"
Write-Output "- Restart-Deployment -Deployment <deployment-name> [-Namespace <namespace>]"
Write-Output "- Check-Volumes"
Write-Output "- Get-ServiceLogs -Service <service-name> [-Namespace <namespace>] [-Tail <lines>]"
Write-Output "- Show-Dashboard"