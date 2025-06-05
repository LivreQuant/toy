Here's the README.md document that outlines the WebSocket communication between the frontend client and backend session service:

```markdown
# WebSocket Communication Protocol

This document outlines how the frontend client and backend session service communicate through WebSocket connections.

## Connection Establishment

The connection is established when the frontend's `ConnectionManager` calls the `connect()` method, which triggers these steps:

1. Frontend retrieves an authentication token and device ID
2. Frontend connects to WebSocket endpoint with query parameters: `token` and `deviceId`
3. Backend authenticates the request in `authenticate_websocket_request()` function
4. After successful connection, backend sends a `connected` message
5. Frontend begins heartbeat cycle

## Message Types Overview

### Client to Server Messages

| Message Type | Purpose | Usage Status |
|--------------|---------|--------------|
| `heartbeat` | Periodic check to maintain connection | Active |
| `reconnect` | Re-establish session after disconnection | Active |
| `request_session_info` | Get current session details | Active |
| `stop_session` | End current session | Active |
| `start_simulator` | Start trading simulator | Active |
| `stop_simulator` | Stop trading simulator | Active |

### Server to Client Messages

| Message Type | Purpose | Usage Status |
|--------------|---------|--------------|
| `connected` | Confirms successful connection | Active |
| `heartbeat_ack` | Response to heartbeat | Active |
| `reconnect_result` | Response to reconnect request | Active |
| `session_info` | Response with session details | Active |
| `session_stopped` | Confirms session termination | Active |
| `simulator_started` | Confirms simulator startup | Active |
| `simulator_stopped` | Confirms simulator shutdown | Active |
| `simulator_status_update` | Async notification of simulator status changes | Active |
| `device_id_invalidated` | Notification that device ID is no longer valid | Active |
| `exchange_data_status` | Market data updates | Potentially underused |
| `exchange_data` | Real-time market data | Potentially underused |
| `shutdown` | Server is shutting down | Active |
| `timeout` | Connection timed out | Active |
| `error` | Error response | Active |

## Detailed Message Flow

### Session Management

1. **Session Information Request/Response**
   - Client sends: `request_session_info`
   ```typescript
   {
     type: 'request_session_info',
     requestId: string,
     timestamp: number,
     deviceId: string
   }
   ```
   - Server responds: `session_info`
   ```typescript
   {
     type: 'session_info',
     requestId: string,
     userId: string,
     status: string,
     deviceId: string,
     createdAt: number,
     expiresAt: number,
     simulatorStatus: string,
     simulatorId: string | null
   }
   ```

2. **Session Termination**
   - Client sends: `stop_session`
   ```typescript
   {
     type: 'stop_session',
     requestId: string,
     timestamp: number,
     deviceId: string
   }
   ```
   - Server responds: `session_stopped`
   ```typescript
   {
     type: 'session_stopped',
     requestId: string,
     success: boolean,
     message: string,
     simulatorStopped: boolean
   }
   ```

### Simulator Management

1. **Start Simulator**
   - Client sends: `start_simulator`
   ```typescript
   {
     type: 'start_simulator',
     requestId: string,
     timestamp: number,
     deviceId: string
   }
   ```
   - Server responds: `simulator_started`
   ```typescript
   {
     type: 'simulator_started',
     requestId: string,
     success: boolean,
     simulatorId: string,
     status: string
   }
   ```

2. **Stop Simulator**
   - Client sends: `stop_simulator`
   ```typescript
   {
     type: 'stop_simulator',
     requestId: string,
     timestamp: number,
     deviceId: string
   }
   ```
   - Server responds: `simulator_stopped`
   ```typescript
   {
     type: 'simulator_stopped',
     requestId: string,
     success: boolean
   }
   ```

3. **Simulator Status Updates**
   - Server sends: `simulator_status_update` (asynchronously)
   ```typescript
   {
     type: 'simulator_status_update',
     simulatorId: string,
     simulatorStatus: string,
     timestamp: number
   }
   ```

### Connection Management

1. **Heartbeat Mechanism**
   - Client sends: `heartbeat`
   ```typescript
   {
     type: 'heartbeat',
     timestamp: number,
     deviceId: string,
     connectionQuality: 'good' | 'degraded' | 'poor',
     sessionStatus: 'active' | 'expired' | 'pending',
     simulatorStatus: 'running' | 'stopped' | 'starting' | 'stopping'
   }
   ```
   - Server responds: `heartbeat_ack`
   ```typescript
   {
     type: 'heartbeat_ack',
     timestamp: number,
     clientTimestamp: number,
     deviceId: string,
     deviceIdValid: boolean,
     connectionQualityUpdate: 'good' | 'degraded' | 'poor',
     sessionStatus: 'valid' | 'invalid' | 'pending',
     simulatorStatus: string
   }
   ```

2. **Reconnection Flow**
   - Client sends: `reconnect`
   ```typescript
   {
     type: 'reconnect',
     deviceId: string,
     sessionToken: string,
     requestId: string
   }
   ```
   - Server responds: `reconnect_result`
   ```typescript
   {
     type: 'reconnect_result',
     requestId: string,
     success: boolean,
     deviceId: string,
     deviceIdValid: boolean,
     message?: string,
     sessionStatus: string,
     simulatorStatus: string
   }
   ```

3. **Device ID Invalidation**
   - Server sends: `device_id_invalidated` (asynchronously)
   ```typescript
   {
     type: 'device_id_invalidated',
     deviceId: string,
     reason?: string,
     timestamp: number
   }
   ```

### Market Data (Potentially Underused)

1. **Exchange Data Updates**
   - Server sends: `exchange_data_status` or `exchange_data`
   ```typescript
   {
     type: 'exchange_data_status',
     timestamp: number,
     symbols: Record<string, {
       price: number,
       change: number,
       volume: number
     }>,
     userOrders?: Record<string, {
       orderId: string,
       status: string,
       filledQty: number
     }>,
     userPositions?: Record<string, {
       symbol: string,
       quantity: number,
       value: number
     }>
   }
   ```

## Potentially Unused or Underused Message Types

1. **Exchange Data Messages**
   - The `exchange_data` and `exchange_data_status` messages are defined but might be underutilized in the current implementation.

2. **Connection Replaced Message**
   - The `connection_replaced` message type is defined and has handlers, but it's not clear if this is actively used.

3. **Error Message Type**
   - While error handling exists, specific error message types might not be consistently used across all interactions.

## Recommendations

1. **Standardize Error Handling**
   - Ensure all request-response pairs have consistent error reporting mechanisms.

2. **Review Market Data Implementation**
   - The market data functionality appears to be implemented but might not be fully utilized.

3. **Document and Standardize Message Schemas**
   - Consider creating a shared schema definition that both frontend and backend can reference.

4. **Enhance Reconnection Strategy**
   - The current implementation has a reconnection mechanism, but it could potentially be enhanced with more robust backoff strategies.
```