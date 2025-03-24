# scripts/simulate-network-issues.ps1
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

# Get the pod names
$podNames = kubectl get pods -l app=$deploymentName -o jsonpath="{.items[*].metadata.name}"

if (-not $podNames) {
    Write-Error "No pods found for $deploymentName"
    exit 1
}

# Apply network issue
foreach ($pod in $podNames.Split()) {
    Write-Output "Applying $IssueType to pod $pod for $DurationSeconds seconds..."
    
    switch ($IssueType) {
        "latency" {
            kubectl exec network-chaos -- tc qdisc add dev eth0 root netem delay 500ms 200ms
        }
        "packet-loss" {
            kubectl exec network-chaos -- tc qdisc add dev eth0 root netem loss 20%
        }
        "partition" {
            $targetIp = kubectl get pod $pod -o jsonpath="{.status.podIP}"
            kubectl exec network-chaos -- iptables -A OUTPUT -d $targetIp -j DROP
        }
    }
    
    # Wait for the specified duration
    Write-Output "Waiting for $DurationSeconds seconds..."
    Start-Sleep -Seconds $DurationSeconds
    
    # Remove the network issue
    Write-Output "Removing network issue..."
    switch ($IssueType) {
        "latency" {
            kubectl exec network-chaos -- tc qdisc del dev eth0 root
        }
        "packet-loss" {
            kubectl exec network-chaos -- tc qdisc del dev eth0 root
        }
        "partition" {
            $targetIp = kubectl get pod $pod -o jsonpath="{.status.podIP}"
            kubectl exec network-chaos -- iptables -D OUTPUT -d $targetIp -j DROP
        }
    }
    
    Write-Output "Network issue removed."
}