# Kubernetes Development Environment

This directory contains Kubernetes configuration files for running the trading platform locally using Minikube.

## Directory Structure

- **deployments/**: Kubernetes deployment configurations for all services
- **storage/**: Persistent volume configurations
- **secrets/**: Kubernetes secret definitions (credentials, tokens)
- **jobs/**: One-time job configurations (e.g., database initialization)

## Getting Started

### Prerequisites

1. Docker Desktop
2. Minikube
3. kubectl
4. PowerShell

### Initial Setup

1. Start Minikube:
minikube start --driver=docker --cpus=4 --memory=8g --disk-size=20g
Copy
2. Run the setup script:
.\scripts\setup-local-env.ps1
Copy
3. Deploy all services:
.\scripts\deploy-services.ps1
Copy
4. Add the following entry to your hosts file (`C:\Windows\System32\drivers\etc\hosts`):
<minikube-ip> trading.local
CopyReplace `<minikube-ip>` with the output of `minikube ip` command.

### Accessing Services

- API: `http://trading.local/api`
- WebSocket: `ws://trading.local/ws`
- PostgreSQL: Connect via PgBouncer at `pgbouncer:5432` inside the cluster

## Configuration Files

### Deployments

- **auth-service.yaml**: Authentication service
- **session-manager.yaml**: Session management service
- **order-service.yaml**: Order processing service
- **exchange-simulator.yaml**: Trading simulator
- **postgres-deployment.yaml**: PostgreSQL database
- **redis-deployment.yaml**: Redis cache
- **pgbouncer.yaml**: Connection pooler for PostgreSQL

### Storage

- **storage.yaml**: Persistent volume configurations

### Secrets

- **db-credentials.yaml**: Database credentials
- **jwt-secret.yaml**: JWT authentication secrets

### Jobs

- **db-init-job.yaml**: Database initialization

## Development Workflow

### Updating a Single Service

To update and restart a specific service:
.\scripts\reset-service.ps1 -Service <service-name>
Copy
Where `<service-name>` is one of: `auth`, `session`, `order`, or `exchange`.

### Full Reset

To reset the entire environment:
.\scripts\reset-minikube.ps1
Copy
Use `-KeepData` flag to preserve data volumes, or `-Full` flag for a complete cluster rebuild.

### Debugging

Helpful debugging commands are available in `debug-commands.ps1`:
. .\scripts\debug-commands.ps1
Copy
## Production Considerations

This setup is for development only. For production on AWS EKS:

1. Use proper secrets management (AWS Secrets Manager)
2. Set up proper IAM roles
3. Use ECR for container images
4. Configure AWS ALB for ingress with HTTPS
5. Set up CloudWatch for logging