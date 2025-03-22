# Session Manager Service Architecture Overview

The Session Manager Service is a critical middleware component that bridges your frontend application with exchange simulators running in AWS EKS. It performs several key functions:

## Core Responsibilities

1. **Session Management**: 
   - Creates, validates, and maintains user sessions
   - Tracks session state across multiple pods in Kubernetes
   - Ensures session affinity when reconnecting users

2. **Protocol Bridging**:
   - Provides both gRPC API for service-to-service communication
   - Offers SSE (Server-Sent Events) endpoints for browser-friendly streaming
   - Translates between these protocols without modifying the underlying business logic

3. **Exchange Service Lifecycle**:
   - Activates exchange simulator instances on demand
   - Manages connections to exchange services
   - Handles graceful termination of unused exchange services

4. **Connection Quality Monitoring**:
   - Tracks connection health metrics
   - Recommends reconnections when quality degrades
   - Handles pod transfers in the Kubernetes environment

## Component Architecture

The service has several key components:

- **gRPC API Handler** (`grpc_session_handler.py`): Handles traditional gRPC endpoints for session management operations.

- **Exchange Gateway** (`exchange_gateway.py`): Manages connections to exchange simulators, including activation, heartbeats, and streaming.

- **SSE Stream Adapter** (`sse_stream_adapter.py`): Bridges gRPC streaming to HTTP/SSE for browser-friendly communication.

- **Session Repository** (`session_storage.py`): Handles persistence of session data in PostgreSQL.

- **Health Endpoints** (`health_endpoints.py`): Provides Kubernetes health and readiness probes.

## Communication Flow

1. **Frontend → Session Manager**: 
   - Browser connects via HTTP/SSE for market data streams
   - Stateless operations use standard HTTP endpoints

2. **Session Manager → Exchange Services**:
   - Uses gRPC for high-performance, bidirectional streaming
   - Converts market data messages between formats

3. **Session Manager → Database**:
   - Persists session state for reliability
   - Enables session recovery across pod failures

## AWS Integration Points

- Works with **AWS ALB/EKS** for load balancing and session affinity
- Handles **CloudFront** proxied connections
- Designed to be resilient to EKS pod rescheduling

This architecture gives you the best of both worlds: high-performance internal communication with gRPC for service-to-service interactions, plus web-friendly browser communication via SSE, all while maintaining the core session management capabilities needed in a distributed Kubernetes environment.