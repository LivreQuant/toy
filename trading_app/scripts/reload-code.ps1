# reload-code.ps1
param (
    [Parameter(Mandatory=$true)]
    [string]$Service
)

$deploymentNames = @{
    "auth" = "auth-service"
    "session" = "session-manager"
    "order" = "order-service"
    "exchange" = "exchange-simulator"
}

if (-not $deploymentNames.ContainsKey($Service)) {
    Write-Error "Unknown service: $Service"
    exit 1
}

$deploymentName = $deploymentNames[$Service]
$podName = $(kubectl get pods -l app=$deploymentName -o jsonpath="{.items[0].metadata.name}")

Write-Output "Restarting pod $podName..."
kubectl delete pod $podName

Write-Output "New pod is starting. Pod status:"
kubectl get pods -l app=$deploymentName -w