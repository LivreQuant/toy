# PostgreSQL Infrastructure

This directory contains the PostgreSQL configuration for the Open Trading Platform.

## Components

- Single PostgreSQL instance (can be scaled for production)
- Metrics enabled for monitoring
- Persistence enabled
- Custom pg_hba configuration

## Installation

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install opentp bitnami/postgresql -f values.yaml --namespace postgresql --create-namespace
```
