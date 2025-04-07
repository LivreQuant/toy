# Project Context: Frontend Migration for Trading Simulator

We're modernizing a trading simulator frontend to improve its reliability and performance in AWS EKS. The current architecture uses gRPC for all communication, which is proving problematic in a Kubernetes environment.

## Goal

Refactor the frontend to use a more web-friendly and resilient approach:
- Replace gRPC with REST APIs for stateless operations
- Add WebSocket support for session management
- Implement SSE (Server-Sent Events) for market data streaming

## Key Services

- **Auth Service**: Login, registration, token management
- **Session Service**: Connection management, exchange simulator control
- **Order Service**: Submit and manage trading orders
- **Exchange Service**: Market data and order execution

## Technical Architecture

1. **REST APIs** for:
   - Authentication
   - Session management
   - Order submission
   - User preferences

2. **WebSockets** for:
   - Session keepalive
   - Connection status
   - Service events

3. **SSE** for:
   - Market data streams
   - Order updates
   - Position changes

## Current Progress

- Identified core components that need refactoring
- Designed new service architecture for improved resilience
- Created implementation plan for HTTP client, WebSocket manager, and SSE client
- Started refactoring the connection management system

## Next Steps

1. Complete the HTTP client implementation
2. Build the WebSocket connection manager
3. Implement SSE client for market data
4. Update React contexts to use the new services
5. Refactor UI components to work with the new data sources

The end result will be a more reliable trading platform with better tolerance for network issues and Kubernetes pod cycling in AWS EKS.