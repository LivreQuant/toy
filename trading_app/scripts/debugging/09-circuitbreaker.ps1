# 09-circuit-breaker.ps1
param (
    [Parameter(Mandatory=$true)]
    [string]$Service,
    
    [Parameter(Mandatory=$false)]
    [int]$DurationSeconds = 30
)

$deploymentNames = @{
    "auth" = "auth-service"
    "session" = "session-manager"
    "order" = "order-service"
    "exchange" = "exchange-simulator"
}

if (-not $deploymentNames.ContainsKey($Service)) {
    Write-Error "Unknown service: $Service. Valid services are: $($deploymentNames.Keys -join ', ')"
    exit 1
}

$deploymentName = $deploymentNames[$Service]

Write-Output "Testing circuit breaker for $deploymentName for $DurationSeconds seconds..."

# Create the network policy to block traffic
$blockNetworkPolicy = @"
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: circuit-breaker-test
spec:
  podSelector:
    matchLabels:
      app: $deploymentName
  policyTypes:
  - Ingress
  - Egress
"@

Write-Output "Applying network policy to isolate $deploymentName..."
$blockNetworkPolicy | kubectl apply -f -

Write-Output "Service is isolated. Circuit breakers should activate after multiple retries."
Write-Output "Waiting for $DurationSeconds seconds..."

# Show countdown
for ($i = $DurationSeconds; $i -gt 0; $i--) {
    Write-Progress -Activity "Circuit Breaker Test" -Status "Time remaining" -SecondsRemaining $i
    Start-Sleep -Seconds 1
}

# Remove the network policy
Write-Output "Removing network policy..."
kubectl delete networkpolicy circuit-breaker-test

Write-Output "Circuit breaker test complete. Service communication should resume."
Write-Output "Note: Depending on your circuit breaker implementation, services may need time to recover."