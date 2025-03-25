# Kubernetes Configuration Files

This directory contains Kubernetes YAML configuration files for deploying the trading platform microservices architecture.

## Directory Structure

- **autoscaling/** - Horizontal Pod Autoscaler configurations
- **aws/** - AWS-specific configurations for EKS deployment
- **config/** - ConfigMaps for database initialization and configuration
- **deployments/** - Service and deployment definitions
- **ingress/** - Ingress controller configuration for routing external traffic
- **jobs/** - One-time job configurations
- **monitoring/** - Prometheus and Grafana monitoring setup
- **network/** - Network policies for security
- **podpolicies/** - Pod disruption budgets for high availability
- **secrets/** - Kubernetes secret definitions
- **storage/** - Persistent volume configurations
- **templates/** - Templates for dynamically created resources
- **tools/** - Admin tools and utilities

## File Descriptions

### Autoscaling

- **hpa.yaml** - Horizontal Pod Autoscaler configurations for automatically scaling services based on CPU utilization (70% threshold) with min/max replicas defined.

### AWS

- **alb-ingress.yaml** - AWS Application Load Balancer ingress configuration for EKS deployment.
- **auth-deployment-aws.yaml** - AWS-specific customizations for auth deployment, including JWT secrets from AWS Secrets Manager.
- **fluent-bit-configmap.yaml** - Logging configuration for shipping logs to AWS CloudWatch.

### Config

- **db-data.yaml** - ConfigMap containing SQL to initialize the database with default data and users.
- **db-schemas.yaml** - ConfigMap containing SQL schemas for database tables, indexes, and stored procedures.

### Deployments

- **auth-service.yaml** - Authentication service deployment and service definition, including database connections and JWT token configuration.
- **postgres-deployment.yaml** - PostgreSQL database deployment with persistent volume for data storage.
- **redis-deployment.yaml** - Redis cache deployment for session and application state storage.
- **pgbouncer.yaml** - PostgreSQL connection pooler to efficiently manage database connections.
- **order-service.yaml** - Order processing service deployment with connections to database and auth service.
- **session-manager.yaml** - Session management service that handles WebSockets, SSE, and manages exchange simulators.
- **session-manager-rbac.yaml** - Role-based access control for session manager to create and manage exchange simulator instances.
- **minio.yaml** - MinIO object storage service for development (S3-compatible).

### Ingress

- **ingress.yaml** - Nginx ingress configuration for routing external traffic to internal services with WebSocket support and sticky sessions.

### Jobs

- **db-init-job.yaml** - One-time job to initialize database schemas and seed data on first deployment.

### Monitoring

- **grafana.yaml** - Grafana dashboard deployment with Prometheus data source configuration.
- **prometheus.yaml** - Prometheus monitoring system deployment with service discovery for metrics collection.

### Network

- **network-policy.yaml** - Network security policies defining allowed communication paths between services.

### Pod Policies

- **pdb.yaml** - Pod Disruption Budgets to ensure minimum availability during voluntary disruptions.

### Secrets

- **db-credentials.yaml** - Database username and password secrets.
- **jwt-secret.yaml** - JWT signing and refresh token secrets for authentication.

### Storage

- **storage.yaml** - Persistent volume and claim definitions for stateful services like PostgreSQL.

### Templates

- **exchange-simulator-template.yaml** - Template for dynamically creating exchange simulator instances, used by the session service.

### Tools

- **admin-dashboard.yaml** - Simple admin dashboard for monitoring and managing the platform.
- **load-tester.yaml** - Load testing tool for performance testing.
- **network-chaos.yaml** - Chaos testing tool for simulating network failures and latency.

## Usage

These configuration files are applied to a Kubernetes cluster using the scripts in the `/scripts` directory. See the main README.md for deployment instructions.

For development, the recommended approach is to use Minikube with the provided scripts rather than applying these files manually.

## Note on Exchange Simulator

The exchange simulator service is not deployed as a regular service. Instead, the session-manager service dynamically creates simulator instances using the template in `templates/exchange-simulator-template.yaml` as users create trading sessions.