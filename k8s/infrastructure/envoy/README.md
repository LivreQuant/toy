# Envoy Infrastructure

This directory contains the Envoy proxy configuration for the Open Trading Platform.

## Components

- Modern Envoy proxy configuration
- gRPC routing setup
- Health checking and monitoring
- Load balancing configuration

## Installation

```bash
# Using official Envoy helm chart instead of deprecated one
helm repo add envoyproxy https://helm.envoyproxy.io
helm install envoy envoyproxy/envoy -f values.yaml --namespace envoy --create-namespace
```
