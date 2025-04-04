# Code Dependencies in the Service Directory

Here's an outline of the dependencies and hierarchy in your service directory, starting from the entry points:

## Entry Points

The main entry points to your service layer are:

1. **ConnectionManager** - Primary service used by `ConnectionContext`
2. **TokenManager** - Used by `AuthContext`
3. **SessionManager** - Used by auth and connection systems

## Dependency Hierarchy

```
ConnectionManager
├── TokenManager
├── WebSocketManager
│   ├── ConnectionStrategy
│   ├── HeartbeatManager
│   ├── WebSocketMessageHandler
│   ├── MetricTracker
│   └── WebSocketErrorHandler
├── ExchangeDataStream
│   └── SSEManager
├── HttpClient
├── UnifiedConnectionState (new proposed component)
├── ConnectionDataHandlers
├── ConnectionSimulatorManager
└── RecoveryManager

TokenManager
└── AuthApi

SessionManager (Static utility class with no direct dependencies)

Authentication Services
├── TokenManager
└── Auth API Services

Notification Services
└── ToastService (Singleton)
```

## Key Service Interactions

1. **ConnectionManager** orchestrates all connection-related services including WebSocket and SSE connections. It's the primary entry point used by your React components through ConnectionContext.

2. **TokenManager** manages authentication tokens and is used by almost every service that makes authenticated requests:
   - All API services
   - WebSocketManager 
   - SSEManager
   - ConnectionManager

3. **WebSocketManager** handles all WebSocket connections and is the primary communication channel:
   - Creates and manages the actual WebSocket connection
   - Handles reconnection logic
   - Processes all WebSocket messages

4. **ExchangeDataStream** manages the SSE connection for streaming data:
   - Depends on WebSocketManager 
   - Only connects when WebSocket is connected
   - Handles market data streaming

5. **SSEManager** is the implementation for SSE connections used by ExchangeDataStream

6. **HttpClient** is used by all API services:
   - Handles REST API requests 
   - Manages authentication headers
   - Handles error responses and retries

7. **RecoveryManager** handles connection recovery:
   - Used by ConnectionManager
   - Coordinates reconnection attempts
   - Manages backoff strategies

This service layer implements a clear hierarchy with ConnectionManager at the top, orchestrating the WebSocket and SSE connections, with TokenManager providing authentication across all services.