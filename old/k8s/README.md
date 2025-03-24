# OpenTP Kubernetes Configuration

This directory contains the modernized Kubernetes configuration for the Open Trading Platform, replacing the previous setup in `install/` and `helm-otp-chart/`.

## Directory Structure

```
k8s/
├── infrastructure/     # Core infrastructure components
│   ├── kafka/         # Message broker
│   ├── postgresql/    # Database
│   └── envoy/         # API Gateway
├── services/          # Application services
│   ├── auth/          # Authentication services
│   ├── market-data/   # Market data services
│   ├── order-management/  # Order processing
│   └── trading/       # Trading venues and simulators
├── config/            # Configuration
│   ├── common/        # Shared configs
│   └── secrets/       # Secret templates
├── rbac/             # Access control
└── scripts/          # Installation scripts
```

## Prerequisites

- Kubernetes cluster (1.24+)
- kubectl configured
- Helm 3 installed
- Docker repository access

## Installation

1. Configure environment:

```bash
# Set required variables
export DOCKER_REPO=ettec
export VERSION=latest
```

With these scripts, your workflow will be:

Build Docker images:
bashCopy./build-images.sh -r your-registry -t latest -c all -p

Deploy to Kubernetes:
bashCopycd k8s
./scripts/deploy.sh -r your-registry -t latest -c all

Cleanup when needed:
bashCopycd k8s
./scripts/cleanup.sh -c all

## Frontend Setup

Add a new file `k8s/services/frontend/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: opentp-client
  labels:
    app: opentp-client
spec:
  replicas: 1
  selector:
    matchLabels:
      app: opentp-client
  template:
    metadata:
      labels:
        app: opentp-client
    spec:
      containers:
        - name: opentp-client
          image: ${DOCKER_REPO}/otp-opentp-client:${VERSION}
          ports:
            - containerPort: 80
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "256Mi"
              cpu: "200m"
```

And `k8s/services/frontend/service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: opentp-client
spec:
  type: NodePort # or LoadBalancer for cloud
  ports:
    - port: 80
      targetPort: 80
  selector:
    app: opentp-client
```

## Still Needed

1. **Service Dependencies**:

   - Add initialization jobs for database schema
   - Add health checks between services
   - Implement proper startup order

2. **Monitoring Setup**:

   - Prometheus configuration
   - Grafana dashboards
   - Alert rules

3. **Additional Infrastructure**:

   - Logging solution (EFK or similar)
   - Backup solutions
   - Disaster recovery plans

4. **Security**:
   - Network policies
   - Secret management solution
   - TLS configuration

## Usage

### Component Installation

```bash
# Install all components
./install-infrastructure.sh
./install-services.sh -c all

# Install specific components
./install-services.sh -c auth
./install-services.sh -c market-data
./install-services.sh -c order-management
./install-services.sh -c trading
```

### Accessing Services

```bash
# Get frontend URL
kubectl get svc opentp-client -o wide

# Get Envoy proxy URL (API Gateway)
kubectl get svc -n envoy envoy -o wide
```

### Monitoring

```bash
# Check service status
kubectl get pods

# View logs
kubectl logs -f deployment/opentp-client
kubectl logs -f deployment/market-data-service
```

## Migration from Old Setup

This new structure replaces:

- `install/install.sh`
- `install/charts/envoy`
- `helm-otp-chart/` directory

Key improvements:

- Modular component installation
- Better resource management
- Modern Kubernetes practices
- Improved maintainability
- Better documentation

````

What's still missing that needs implementation:

1. **Database Initialization**:
Create a job to handle database schema and initial data:
```yaml
# k8s/infrastructure/postgresql/init-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: db-init
spec:
  template:
    spec:
      containers:
      - name: db-init
        image: ${DOCKER_REPO}/otp-dataload:${VERSION}
        env:
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgresql
              key: postgres-password
````

2. **Monitoring Stack**:
   Add Prometheus and Grafana configurations in:

```
k8s/monitoring/
├── prometheus/
├── grafana/
└── alertmanager/
```

3. **Development Tools**:
   Add development support:

- Skaffold configuration
- Kustomize overlays
- Local development scripts
