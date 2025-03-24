# Market Data Services

This directory contains the Kubernetes configurations for the market data related services:

## Components

- market-data-service: Main market data service
- market-data-gateway: FIX protocol gateway for market data
- quote-aggregator: Service for aggregating quotes from multiple sources

## Dependencies

- Kafka infrastructure
- Envoy proxy for API routing
- Trading services RBAC configuration

## Configuration

Services use configuration from:

- Common ConfigMap (opentp-common)
- Service-specific ConfigMaps
