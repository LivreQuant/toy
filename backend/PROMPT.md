# Kubernetes Backend Framework for Trading Platform

I need help setting up a Kubernetes deployment for my trading platform that consists of four microservices:

1. **auth-service** (port 8000): Handles authentication and authorization with JWT tokens
   - Needs PostgreSQL for user data
   - Environment variables: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `JWT_SECRET`, `JWT_EXPIRY`

2. **session-service** (port 8080): Manages client sessions and acts as a bridge between frontend and exchange
   - Handles WebSocket connections (port 8080), SSE streams, and REST API
   - Creates/manages exchange simulators for users
   - Environment variables: `REDIS_HOST`, `REDIS_PORT`, `AUTH_SERVICE_URL`, `EXCHANGE_MANAGER_SERVICE`

3. **order-service** (port 8001): Processes trading orders
   - Validates and routes orders to the appropriate exchange simulator
   - Stores order history in PostgreSQL
   - Environment variables: `DB_HOST`, `DB_PORT`, `DB_NAME`, `REDIS_HOST`, `REDIS_PORT`, `AUTH_SERVICE_URL`

4. **exchange-service** (port 50055): Simulates market data and executes trades
   - Uses gRPC for high-performance communication
   - Provides real-time market data streams
   - Environment variables: `PORT`, `HOST`, `INACTIVITY_TIMEOUT_SECONDS`, `AUTO_TERMINATE`

I need guidance on:
1. Setting up a proper Kubernetes deployment with appropriate resource limits
2. Configuring service discovery between microservices
3. Setting up persistent storage for PostgreSQL and Redis
4. Configuring network policies for secure communication
5. Implementing proper liveness and readiness probes for each service
6. Establishing horizontal scaling policies, particularly for session-service and exchange-service

I'm deploying on AWS EKS and need to consider cloud-specific optimizations. The frontend will connect via an Application Load Balancer (ALB) that should properly route WebSocket, SSE, and REST traffic.