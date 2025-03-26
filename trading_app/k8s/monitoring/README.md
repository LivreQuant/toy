# Kubernetes Monitoring and Tracing Tools for Trading Platform

This guide presents the most useful tools for monitoring and debugging your Kubernetes trading platform, arranged in order of importance. Each tool addresses specific observability needs, from high-level service tracing to low-level network packet inspection.

## 1. Jaeger - Distributed Tracing

**Purpose:** Track requests as they flow through your microservices, with ability to filter by user ID or session ID.

**Why it's essential:** Helps you understand the complete journey of user requests through your trading platform, identifying performance bottlenecks and errors.

### Setup Instructions

```bash
# Install Jaeger operator
kubectl apply -f https://github.com/jaegertracing/jaeger-operator/releases/download/v1.35.0/jaeger-operator.yaml

# Wait for the operator to be ready
kubectl wait --for=condition=available deployment/jaeger-operator -n observability --timeout=90s

# Deploy Jaeger instance
cat > jaeger.yaml << EOF
apiVersion: jaegertracing.io/v1
kind: Jaeger
metadata:
  name: trading-jaeger
spec:
  strategy: allInOne
  allInOne:
    image: jaegertracing/all-in-one:latest
    options:
      log-level: info
  storage:
    type: memory
    options:
      memory:
        max-traces: 100000
  ingress:
    enabled: true
    hosts:
      - trading.local
    path: /jaeger
EOF

kubectl apply -f jaeger.yaml
```

**Service Instrumentation:**
- Add OpenTracing/OpenTelemetry libraries to your services
- Configure them to send spans to the Jaeger collector
- Ensure user IDs and session IDs are added to spans as tags

**Access:** http://trading.local/jaeger

## 2. Prometheus & Grafana - Metrics & Dashboards

**Purpose:** Collect and visualize metrics from all services in your trading platform.

**Why it's important:** Provides real-time visibility into system health, performance trends, and anomalies.

### Setup Instructions

```bash
# Deploy Prometheus and Grafana from your existing configurations
kubectl apply -f k8s/monitoring/prometheus.yaml
kubectl apply -f k8s/monitoring/grafana.yaml

# Create custom dashboard for trading platform
cat > trading-dashboard.yaml << EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: trading-dashboard
  labels:
    grafana_dashboard: "1"
data:
  trading-dashboard.json: |
    {
      "annotations": { "list": [] },
      "editable": true,
      "panels": [
        {
          "datasource": "Prometheus",
          "fieldConfig": { "defaults": {}, "overrides": [] },
          "gridPos": { "h": 8, "w": 12, "x": 0, "y": 0 },
          "id": 1,
          "options": {},
          "targets": [
            {
              "expr": "rate(http_requests_total{service=~\"auth-service|order-service|session-manager\"}[5m])",
              "interval": "",
              "legendFormat": "{{service}} - {{path}}",
              "refId": "A"
            }
          ],
          "title": "Request Rate by Service",
          "type": "timeseries"
        }
      ],
      "refresh": "10s",
      "schemaVersion": 16,
      "style": "dark",
      "tags": ["trading"],
      "templating": { "list": [] },
      "time": { "from": "now-1h", "to": "now" },
      "timepicker": {},
      "timezone": "",
      "title": "Trading Platform Dashboard",
      "uid": "trading-platform",
      "version": 1
    }
EOF

kubectl apply -f trading-dashboard.yaml
```

**Service Instrumentation:**
- Add Prometheus client libraries to your services
- Expose metrics endpoints (typically on /metrics)
- Track custom metrics like active sessions, order processing time, etc.

**Access:** 
- Prometheus: http://trading.local/prometheus
- Grafana: http://trading.local/grafana

## 3. Loki - Centralized Logging

**Purpose:** Aggregate logs from all services and provide log search and analysis.

**Why it's valuable:** Enables correlation of events across services, making it easier to troubleshoot issues.

### Setup Instructions

```bash
# Create a values file for Loki
cat > loki-values.yaml << EOF
loki:
  persistence:
    enabled: true
    size: 5Gi
promtail:
  config:
    snippets:
      extraScrapeConfigs: |
        - job_name: container_logs
          kubernetes_sd_configs:
            - role: pod
EOF

# Install Loki and Promtail using Helm
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
helm install loki grafana/loki-stack -f loki-values.yaml
```

**Configuration:**
- Add Loki as a data source in Grafana
- Create log dashboards in Grafana
- Configure structured logging in your services

**Access:** Through Grafana after adding Loki as a data source

## 4. Istio & Kiali - Service Mesh & Network Visualization

**Purpose:** Visualize service connectivity and network traffic flows.

**Why it's useful:** Provides a dynamic view of how services interact, with detailed metrics on request volumes, error rates, and latencies.

### Setup Instructions

```bash
# Download and install Istio
curl -L https://istio.io/downloadIstio | sh -
cd istio-*
./bin/istioctl install --set profile=demo

# Label namespace for Istio injection
kubectl label namespace default istio-injection=enabled

# Install Kiali dashboard
kubectl apply -f samples/addons/kiali.yaml

# Restart your deployments to inject Istio sidecars
kubectl rollout restart deployment auth-service session-manager order-service
```

**Access:** Access Kiali at http://trading.local/kiali (after configuring ingress)

## 5. Cilium Hubble - Network Flow Monitoring

**Purpose:** Monitor network flows between pods at the packet level.

**Why it's useful:** Provides deep visibility into network communications, helping identify connectivity issues and policy violations.

### Setup Instructions

```bash
# Install Cilium CLI
curl -L --remote-name-all https://github.com/cilium/cilium-cli/releases/latest/download/cilium-linux-amd64.tar.gz
sudo tar xzvfC cilium-linux-amd64.tar.gz /usr/local/bin

# Install Cilium with Hubble enabled
cilium install --version 1.12.1 --set hubble.relay.enabled=true --set hubble.ui.enabled=true

# Enable Hubble
cilium hubble enable --ui

# Port-forward to access Hubble UI
kubectl port-forward -n kube-system svc/hubble-ui 12000:80
```

**Access:** http://localhost:12000 (when port-forwarding is active)

## 6. tcpdump & Wireshark - Packet Analysis

**Purpose:** Capture and analyze network packets for detailed inspection.

**Why it's useful:** Provides the lowest-level visibility into raw network traffic when other tools don't provide enough detail.

### Usage Instructions

```bash
# Install tcpdump in your pods (if not already present)
kubectl exec -it <pod-name> -- apt-get update && apt-get install -y tcpdump

# Capture traffic from a specific user IP
kubectl exec -it <pod-name> -- tcpdump -i any host <user-ip-address> -w /tmp/capture.pcap

# Copy the capture file locally
kubectl cp <pod-name>:/tmp/capture.pcap ./capture.pcap

# Open with Wireshark
wireshark capture.pcap
```

**Best for:** Last-resort debugging when higher-level tools don't reveal the issue.

## Implementation Strategy

1. Start with **Jaeger** to get immediate visibility into request flows
2. Deploy **Prometheus & Grafana** for metrics visualization
3. Add **Loki** for centralized logging
4. Implement **Istio & Kiali** if you need more detailed service mesh capabilities
5. Add **Cilium Hubble** for network flow monitoring
6. Use **tcpdump & Wireshark** when needed for packet-level analysis

Each tool builds on the previous one to provide increasingly detailed visibility into your trading platform's behavior, making it easier to monitor performance, troubleshoot issues, and trace individual user interactions through the system.