Here's a comprehensive overview of the APIs your backend services are exposing to your frontend application:

## Authentication Service (auth-service)

### Authentication Endpoints

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| POST | `/api/auth/login` | Authenticate user | `{username, password}` | `{success, accessToken, refreshToken, expiresIn}` |
| POST | `/api/auth/logout` | Log out | `{accessToken, refreshToken, logoutAll}` | `{success}` |
| POST | `/api/auth/refresh` | Refresh token | `{refreshToken}` | `{success, accessToken, expiresIn}` |
| POST | `/api/auth/validate` | Validate token | `{token}` or Bearer header | `{valid, userId, user_role}` |

## Session Service (session-service)

### Session Management

| Method | Endpoint | Description | Request Body/Params | Response |
|--------|----------|-------------|---------------------|----------|
| POST | `/api/sessions` | Create a session | `{userId, token}` | `{success, sessionId, isNew}` |
| GET | `/api/sessions/{session_id}` | Get session details | Query: `token` | `{success, session}` |
| DELETE | `/api/sessions/{session_id}` | End a session | `{token}` | `{success}` |
| POST | `/api/sessions/{session_id}/reconnect` | Reconnect to session | `{token, attempt}` | `{success, session}` |

### Simulator Management

| Method | Endpoint | Description | Request Body/Params | Response |
|--------|----------|-------------|---------------------|----------|
| POST | `/api/simulators` | Start simulator | `{sessionId, token}` | `{success, simulatorId, endpoint}` |
| DELETE | `/api/simulators/{simulator_id}` | Stop simulator | `{sessionId, token}` | `{success}` |
| GET | `/api/simulators/{simulator_id}` | Get simulator status | Query: `token, sessionId` | `{success, status}` |

### Real-time Connections

| Method | Endpoint | Description | Query Parameters | Protocol |
|--------|----------|-------------|------------------|----------|
| GET | `/ws` | WebSocket connection | `sessionId, token, clientId` | WebSocket |
| GET | `/stream` | Market data stream | `sessionId, token, symbols, clientId` | Server-Sent Events (SSE) |

## Order Service (order-service)

### Order Management

| Method | Endpoint | Description | Request Body/Params | Response |
|--------|----------|-------------|---------------------|----------|
| POST | `/api/orders/submit` | Submit an order | `{sessionId, symbol, side, quantity, type, price?, requestId?}` | `{success, orderId}` |
| POST | `/api/orders/cancel` | Cancel an order | `{orderId, sessionId}` | `{success}` |
| GET | `/api/orders/status` | Get order status | Query: `orderId, sessionId` | `{success, status, filledQuantity, avgPrice}` |
| GET | `/api/orders/user` | Get user orders | Query: `limit, offset` | `{success, orders, count, limit, offset}` |

## Health and Monitoring (All Services)

| Method | Endpoint | Description | Response |
|--------|----------|-------------|----------|
| GET | `/health` | Health check | `{status: "UP", timestamp}` |
| GET | `/readiness` | Readiness check | `{status, checks}` |

## WebSocket Protocol

### Client to Server Messages

| Message Type | Payload | Description |
|--------------|---------|-------------|
| `heartbeat` | `{timestamp}` | Client heartbeat |
| `connection_quality` | `{token, latencyMs, missedHeartbeats, connectionType}` | Connection quality report |
| `simulator_action` | `{token, action}` | Control simulator ("start" or "stop") |
| `reconnect` | `{token, attempt}` | Reconnection request |

### Server to Client Messages

| Message Type | Payload | Description |
|--------------|---------|-------------|
| `connected` | `{sessionId, clientId, podName, timestamp}` | Connection established |
| `heartbeat_ack` | `{timestamp, clientTimestamp, latency}` | Heartbeat response |
| `connection_quality_update` | `{quality, reconnectRecommended}` | Connection status |
| `simulator_update` | `{action, status, simulatorId}` | Simulator status change |
| `error` | `{error}` | Error message |

## SSE Events

| Event Type | Data | Description |
|------------|------|-------------|
| `connected` | `{sessionId, clientId}` | Connection established |
| `market-data` | Market data objects | Real-time market data updates |
| `close` | `{reason}` | Stream closing |

## Authentication Notes

- Most API endpoints require authentication via JWT tokens
- Use the `Authorization: Bearer <token>` header or include `token` in request body/query
- Session endpoints require both a valid session ID and authentication token
- WebSocket and SSE streams require session ID and token in query parameters

## Response Format

All REST endpoints follow a consistent response format:
- Success responses: `{success: true, ...additional data}`
- Error responses: `{success: false, error: "Error message"}`

This API set connects your React frontend with your backend microservices for a complete trading platform experience, supporting authentication, session management, market data streaming, and order execution.