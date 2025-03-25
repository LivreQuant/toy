# 08-apply-all-configs.ps1
param (
    [Parameter(Mandatory=$false)]
    [string[]]$Components = @("deployments", "storage", "network", "ingress", "monitoring")
)

Write-Output "Applying Kubernetes configurations..."

# Point to Minikube's Docker daemon
minikube docker-env | Invoke-Expression

# Helper function to apply configurations
function Apply-Configs {
    param (
        [string]$Path
    )
    
    if (Test-Path $Path) {
        $files = Get-ChildItem -Path $Path -Filter "*.yaml"
        foreach ($file in $files) {
            Write-Output "Applying $($file.FullName)..."
            kubectl apply -f $file.FullName
        }
    } else {
        Write-Warning "Path not found: $Path"
    }
}

# Apply configurations based on selected components
foreach ($component in $Components) {
    Write-Output "Applying $component configurations..."
    
    switch ($component) {
        "deployments" {
            Apply-Configs -Path "./k8s/deployments"
        }
        "storage" {
            Apply-Configs -Path "./k8s/storage"
        }
        "network" {
            Apply-Configs -Path "./k8s/network"
        }
        "ingress" {
            Apply-Configs -Path "./k8s/ingress"
            # If using base directory for ingress
            kubectl apply -f "./k8s/ingress.yaml" -ErrorAction SilentlyContinue
        }
        "secrets" {
            Apply-Configs -Path "./k8s/secrets"
        }
        "monitoring" {
            Apply-Configs -Path "./k8s/monitoring"
        }
        "autoscaling" {
            Apply-Configs -Path "./k8s/autoscaling"
        }
        "podpolicies" {
            Apply-Configs -Path "./k8s/podpolicies"
        }
        default {
            Write-Warning "Unknown component: $component"
        }
    }
}

Write-Output "Configuration update complete. Checking deployment status..."
kubectl get pods