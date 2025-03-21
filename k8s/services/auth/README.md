# Authentication Services

This directory contains the Kubernetes configurations for authentication-related services:

## Components

- authorization-service: Handles user authentication and token management
- client-config-service: Manages client configurations and settings

## Dependencies

- PostgreSQL database
- Envoy proxy for API routing
- Trading services RBAC configuration

## Configuration

Services use configuration from:

- Common ConfigMap (opentp-common)
- Auth-specific ConfigMap (auth-service-config)

## Notes

- Authorization service maintains client IP affinity for session consistency
- Client config service is horizontally scalable
