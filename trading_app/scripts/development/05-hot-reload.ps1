# scripts/hot-reload.ps1
param (
    [Parameter(Mandatory=$true)]
    [string]$Service
)

$servicePaths = @{
    "auth" = "./interface/authorization-service"
    "session" = "./interface/session-manager-service"
    "order" = "./interface/order-service"
    "exchange" = "./interface/exchange-manager-service"
}

if (-not $servicePaths.ContainsKey($Service)) {
    Write-Error "Unknown service: $Service"
    exit 1
}

$path = $servicePaths[$Service]

Write-Output "Starting hot reload for $Service. Press Ctrl+C to stop."

# Point to Minikube's Docker daemon
minikube docker-env | Invoke-Expression

# Use a filesystem watcher to detect changes
$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = $path
$watcher.IncludeSubdirectories = $true
$watcher.EnableRaisingEvents = $true

# Define what happens when a file changes
$action = {
    $path = $event.SourceEventArgs.FullPath
    $changeType = $event.SourceEventArgs.ChangeType
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    
    # Skip if this is a temporary file or not a relevant file type
    if ($path -match "\.(tmp|log|bak|git)$") {
        return
    }
    
    Write-Output "$timestamp - $path was $changeType"
    
    # Wait a bit to ensure all file writes are complete
    Start-Sleep -Seconds 1
    
    try {
        # Rebuild and redeploy the service
        & "$PSScriptRoot\reset-service.ps1" -Service $Service
    } catch {
        Write-Error "Error rebuilding service: $_"
    }
}

# Register event handlers
$handlers = @()
$handlers += Register-ObjectEvent -InputObject $watcher -EventName Created -Action $action
$handlers += Register-ObjectEvent -InputObject $watcher -EventName Changed -Action $action

try {
    # Keep script running until Ctrl+C
    while ($true) { Start-Sleep -Seconds 1 }
} finally {
    # Clean up
    $watcher.EnableRaisingEvents = $false
    $handlers | ForEach-Object { Unregister-Event -SubscriptionId $_.Id }
    $watcher.Dispose()
    Write-Output "Hot reload stopped."
}