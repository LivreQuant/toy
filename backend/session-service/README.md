# Session Service Flow Diagram

The session service is a backend component that manages user sessions, handles connection management through WebSockets, and orchestrates exchange simulators. Here's a flow diagram of how the system works:

## Startup Flow

1. **Initialization (main.py)**
   - Configures logging, tracing, and metrics
   - Creates SessionServer instance
   - Calls initialize() and start()
   - Sets up signal handlers for graceful shutdown

2. **Server Initialization (server.py)**
   - Initializes core components:
     - DatabaseManager (PostgreSQL + Redis)
     - AuthClient
     - ExchangeClient
     - SessionManager
     - WebSocketManager
   - Sets up routes (REST API, WebSocket, health endpoints)
   - Configures middleware (metrics, tracing)
   - Configures CORS

3. **Background Tasks Start**
   - Session cleanup task (expired sessions)
   - Simulator heartbeat task
   - WebSocket cleanup task (stale connections)

## Request Flows

### REST API Flow (Session Creation)

1. Client sends HTTP POST to `/api/sessions` with device ID and auth token
2. Request passes through middleware (metrics_middleware, tracing_middleware)
3. `handle_create_session` extracts token and device ID
4. AuthClient validates token and extracts user ID
5. SessionManager.create_session:
   - Checks for existing sessions
   - Creates new session in database
   - Sets metadata (device ID, pod name)
   - Updates metrics
   - Sends events via Redis
6. Response with session ID sent to client

### WebSocket Connection Flow

1. Client connects to `/ws` with session ID, device ID, and token
2. WebSocketManager.handle_connection processes request
3. Authentication via authenticate_websocket_request:
   - Validates token
   - Verifies session
   - Creates session if needed
4. WebSocketRegistry registers connection
5. WebSocketManager sends 'connected' message to client
6. WebSocketDispatcher processes incoming messages:
   - Heartbeat messages
   - Reconnect messages
7. WebSocketManager handles outbound messages:
   - Exchange data updates
   - Error messages
   - Connection state messages

### Simulator Management Flow

1. Client requests simulator start via REST API or WebSocket
2. SessionManager.simulator_ops.start_simulator:
   - Validates session
   - Checks existing simulators
   - Creates new simulator record
3. SimulatorManager.create_simulator:
   - Creates database record
   - Provisions Kubernetes deployment via KubernetesClient
   - Starts simulator via ExchangeClient (gRPC)
4. WebSocket clients receive simulator status updates
5. Exchange data streams from simulator to clients via WebSocket

## Data Flow Between Components

- **SessionManager**: Central coordinator that delegates to specialized components
  - session_ops: Handles session lifecycle
  - simulator_ops: Manages simulator lifecycle
  - reconnection: Handles client reconnection logic
  - connection_quality: Assesses connection health

- **DatabaseManager**: Data persistence layer
  - PostgreSQL: Primary storage for sessions and simulators
  - Redis: Caching, real-time updates, cross-pod coordination

- **WebSocketManager**: Manages client connections
  - WebSocketRegistry: Tracks active connections
  - WebSocketDispatcher: Routes incoming messages
  - StreamManager: Manages background streams
  - Emitters: Formats and sends outbound messages

- **CircuitBreaker**: Prevents cascading failures when calling external services

## Shutdown Flow

1. Signal handler or explicit shutdown call triggers server.shutdown()
2. Server stops accepting new connections
3. _cleanup_pod_sessions:
   - Identifies sessions managed by this pod
   - Stops associated simulators
   - Updates session metadata
   - Notifies clients to reconnect
4. Components close connections:
   - WebSocketManager closes all client connections
   - External clients (AuthClient, ExchangeClient)
   - Database connections
5. Background tasks are cancelled
6. server.shutdown_event is set, allowing wait_for_shutdown() to complete

This architecture enables reliable session management and real-time data exchange between clients and simulators, with graceful error handling and proper cleanup of resources.