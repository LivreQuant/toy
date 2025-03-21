# Order Management Services

This directory contains the Kubernetes configurations for order management related services:

## Components

- order-router: Routes orders to appropriate execution venues
- order-monitor: Monitors and tracks order status
- order-data-service: Manages order data persistence and retrieval

## Dependencies

- Kafka infrastructure for order messaging
- PostgreSQL database for order data
- Trading services RBAC configuration

## Configuration

Services use configuration from:

- Common ConfigMap (opentp-common)

## Notes

- order-router has higher resource allocations due to order processing demands
- order-monitor includes Prometheus metrics
- order-data-service is horizontally scalable
