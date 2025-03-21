# Kafka Infrastructure

This directory contains the Kafka configuration for the Open Trading Platform.

## Components

- Kafka cluster with 3 replicas
- Zookeeper (managed by Kafka chart)
- Metrics enabled for monitoring
- Auto-creation of required topics

## Installation

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install kafka-opentp bitnami/kafka -f values.yaml --namespace kafka --create-namespace
```
