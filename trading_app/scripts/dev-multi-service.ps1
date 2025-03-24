# scripts/dev-multi-service.ps1
param (
    [Parameter(Mandatory=$true)]
    [string[]]$Services,
    
    [switch]$Watch
)

# Setup environment first
Write-Output "Setting up development environment..."
minikube docker-env | Invoke-Expression

# Build and deploy each service
foreach ($service in $Services) {
    Write-Output "Building and deploying $service..."
    .\scripts\reset-service.ps1 -Service $service
}

# If watch flag is set, monitor all services
if ($Watch) {
    Write-Output "Starting file watchers for all services..."
    
    # Launch a watcher for each service
    $processes = @()
    
    foreach ($service in $Services) {
        $processInfo = New-Object System.Diagnostics.ProcessStartInfo
        $processInfo.FileName = "powershell.exe"
        $processInfo.Arguments = "-NoExit -File `"$PSScriptRoot\hot-reload.ps1`" -Service $service"
        $processInfo.WorkingDirectory = (Get-Location).Path
        
        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $processInfo
        $process.Start() | Out-Null
        
        $processes += $process
        
        Write-Output "Started watcher for $service (PID: $($process.Id))"
    }
    
    Write-Output "Watching all services. Press Enter to stop all watchers."
    Read-Host
    
    # Stop all watchers
    foreach ($process in $processes) {
        if (-not $process.HasExited) {
            Write-Output "Stopping watcher (PID: $($process.Id))..."
            Stop-Process -Id $process.Id -Force
        }
    }
    
    Write-Output "All watchers stopped."
}