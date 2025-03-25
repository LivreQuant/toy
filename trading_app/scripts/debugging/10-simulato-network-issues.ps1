# 10-simulate-network-issues.ps1
param (
    [Parameter(Mandatory=$true)]
    [string]$Service,
    
    [Parameter(Mandatory=$true)]
    [ValidateSet("latency", "packet-loss", "partition")]
    [string]$IssueType,
    
    [Parameter(Mandatory=$false)]
    [int]$DurationSeconds = 60
)

$deploymentName = @{
    "auth" = "auth-service"
    "session" = "session-manager"
    "order" = "order-service"
    "exchange" = "exchange-simulator"
}[$Service]

if (-not $deploymentName) {
    Write-Error "Unknown service: $Service"
    exit 1
}

# Ensure network-chaos pod is running
$networkChaosExists = kubectl get pods -l app=network-chaos --no-headers
if (-not $networkChaosExists) {
    Write-Output "Creating network-chaos pod..."
    kubectl apply -f ./k8s/tools/network-chaos.yaml
    Start-Sleep -Seconds 10
}

# Get the pod name
$podName = kubectl get pods -l app=$deploymentName -o jsonpath="{.items[0].metadata.name}"

if (-not $podName) {
    Write-Error "No pods found for $deploymentName"
    exit 1
}

# Get target pod IP
$targetIp = kubectl get pod $podName -o jsonpath="{.status.podIP}"
$networkChaosPod = kubectl get pods -l app=network-chaos -o jsonpath="{.items[0].metadata.name}"

# Apply network issue
Write-Output "Applying $IssueType to pod $podName for $DurationSeconds seconds..."

switch ($IssueType) {
    "latency" {
        kubectl exec $networkChaosPod -- tc qdisc add dev eth0 root netem delay 500ms 200ms
    }
    "packet-loss" {
        kubectl exec $networkChaosPod -- tc qdisc add dev eth0 root netem loss 20%
    }
    "partition" {
        kubectl exec $networkChaosPod -- iptables -A OUTPUT -d $targetIp -j DROP
    }
}

# Wait for the specified duration
Write-Output "Network issue applied. Waiting for $DurationSeconds seconds..."
for ($i = $DurationSeconds; $i -gt 0; $i--) {
    Write-Progress -Activity "Network Issue Simulation" -Status "Time remaining" -SecondsRemaining $i
    Start-Sleep -Seconds 1
}

# Remove the network issue
Write-Output "Removing network issue..."
switch ($IssueType) {
    "latency" {
        kubectl exec $networkChaosPod -- tc qdisc del dev eth0 root
    }
    "packet-loss" {
        kubectl exec $networkChaosPod -- tc qdisc del dev eth0 root
    }
    "partition" {
        kubectl exec $networkChaosPod -- iptables -D OUTPUT -d $targetIp -j DROP
    }
}

Write-Output "Network issue removed. Normal traffic should resume."