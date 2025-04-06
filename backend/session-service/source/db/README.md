# Session Service Database Documentation

This document outlines the database schema, tables, and functions used by the Session Service.

## Overview

The Session Service uses PostgreSQL for persistent storage and manages the following data:

1. User sessions (creation, validation, expiration)
2. Session metadata (connection quality, frontend details, etc.)
3. Simulator instances (creation, tracking, cleanup)

## Schemas

### 1. `session` Schema

This schema contains tables related to user sessions.

#### Tables

##### `active_sessions`

Stores information about active user sessions.

```sql
CREATE TABLE session.active_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    token TEXT
);
```

Fields:
- `session_id`: Unique identifier for the session (UUID)
- `user_id`: User ID associated with the session
- `status`: Current status of the session (ACTIVE, RECONNECTING, INACTIVE, EXPIRED)
- `created_at`: Timestamp when the session was created
- `last_active`: Timestamp of the last activity in the session
- `expires_at`: Timestamp when the session will expire
- `token`: Authentication token (optional)

Indexes:
- `idx_sessions_user_id`: For efficient lookups by user ID
- `idx_sessions_expires_at`: For efficient cleanup of expired sessions

##### `session_metadata`

Stores additional metadata associated with each session.

```sql
CREATE TABLE session.session_metadata (
    session_id TEXT PRIMARY KEY REFERENCES session.active_sessions(session_id) ON DELETE CASCADE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
```

Fields:
- `session_id`: References the session in `active_sessions`
- `metadata`: JSONB field containing various session metadata including:
  - `pod_name`: Name of the pod handling the session
  - `ip_address`: Client IP address
  - `frontend_connections`: Number of active WebSocket connections
  - `connection_quality`: Quality status (GOOD, DEGRADED, POOR)
  - `simulator_id`: ID of the associated exchange simulator
  - `simulator_endpoint`: Endpoint of the simulator service
  - `simulator_status`: Current status of the simulator
  - And other dynamic properties

### 2. `simulator` Schema

This schema contains tables related to exchange simulator instances.

#### Tables

##### `instances`

Tracks exchange simulator instances.

```sql
CREATE TABLE simulator.instances (
    simulator_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES session.active_sessions(session_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL,
    endpoint TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    initial_symbols JSONB,
    initial_cash FLOAT NOT NULL DEFAULT 100000.0
);
```

Fields:
- `simulator_id`: Unique identifier for the simulator instance (UUID)
- `session_id`: Session ID this simulator is associated with
- `user_id`: User ID who owns this simulator
- `status`: Current status (CREATING, STARTING, RUNNING, STOPPING, STOPPED, ERROR)
- `endpoint`: Service endpoint for this simulator
- `created_at`: Timestamp when the simulator was created
- `last_active`: Timestamp of last activity
- `initial_symbols`: JSON array of initial stock symbols
- `initial_cash`: Initial cash amount for the portfolio

Indexes:
- `idx_simulator_session_id`: For efficient lookups by session ID
- `idx_simulator_user_id`: For efficient lookups by user ID
- `idx_simulator_status`: For filtering by status

## Functions

### `session.cleanup_expired_sessions()`

Function to remove expired sessions.

```sql
CREATE OR REPLACE FUNCTION session.cleanup_expired_sessions()
```

# Session Service Database Documentation (continued)

## Functions (continued)

### `session.cleanup_expired_sessions()`

Function to remove expired sessions.

```sql
CREATE OR REPLACE FUNCTION session.cleanup_expired_sessions() 
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM session.active_sessions
    WHERE expires_at < NOW();
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;
```

Purpose:
- Deletes all session records where the expiration time has passed
- Returns the count of deleted sessions
- Due to CASCADE constraints, this also removes associated metadata and simulator records

## Database Operations by the Session Service

The Session Service performs the following database operations:

### Session Management

1. **Create Session**
   - Creates a new session record in `active_sessions`
   - Initializes associated metadata in `session_metadata`
   - Checks for existing active sessions for the user

2. **Get Session**
   - Retrieves session data with metadata
   - Used for validation and session restoration

3. **Update Session Activity**
   - Updates `last_active` and extends `expires_at` timestamp
   - Prevents session expiration for active users

4. **End Session**
   - Explicitly terminates a session
   - Stops associated simulator instances
   - Removes session records

5. **Update Session Metadata**
   - Updates various metadata fields like connection quality
   - Tracks WebSocket connections, SSE streams, etc.

### Simulator Management

1. **Create Simulator**
   - Creates a new simulator record in `simulator.instances`
   - Links it to a session
   - Initializes with configuration (symbols, cash)

2. **Get Simulator**
   - Retrieves simulator data by ID or session ID
   - Used to check status and connect to simulator

3. **Update Simulator Status**
   - Tracks simulator lifecycle states
   - Updates `status` field

4. **Update Simulator Activity**
   - Updates `last_active` timestamp
   - Prevents premature cleanup of active simulators

5. **Cleanup Inactive Simulators**
   - Identifies simulators with no recent activity
   - Marks them as STOPPED
   - Triggers Kubernetes cleanup of associated resources

## Data Relationships

- Each **User** can have multiple **Sessions**
- Each **Session** has exactly one **Metadata** record
- Each **Session** can have at most one active **Simulator**
- **Simulators** are tied to their parent **Session** via foreign key constraints

## Cleanup Processes

The Session Service runs the following automated cleanup processes:

1. **Session Cleanup**
   - Periodically calls `session.cleanup_expired_sessions()`
   - Removes sessions that have exceeded their expiration time

2. **Simulator Cleanup**
   - Identifies simulators that have been inactive for a configurable time period
   - Marks them as STOPPED and removes Kubernetes resources
   - Helps prevent resource leaks

## Notes for Developers

- All time-based fields use `timestamp with time zone` PostgreSQL type
- All UUIDs are stored as text for compatibility
- Foreign key constraints ensure referential integrity
- Cascade delete ensures proper cleanup when sessions are removed
- The JSONB `metadata` field allows for flexible storage of session properties
- Database operations should handle connection failures with retry logic
- When working with simulators, always update the `last_active` field to prevent premature cleanup

## Example Queries

### Check Active Sessions for a User

```sql
SELECT s.session_id, s.created_at, s.last_active, s.expires_at, 
       m.metadata->>'simulator_id' as simulator_id
FROM session.active_sessions s
JOIN session.session_metadata m ON s.session_id = m.session_id
WHERE s.user_id = '<user_id>' AND s.expires_at > NOW();
```

### Find Inactive Simulators

```sql
SELECT simulator_id, session_id, user_id, status, 
       EXTRACT(EPOCH FROM (NOW() - last_active)) as seconds_inactive
FROM simulator.instances
WHERE status != 'STOPPED' 
AND last_active < NOW() - INTERVAL '1 hour';
```

### Check Session Connection Statistics

```sql
SELECT s.session_id, 
       (m.metadata->>'frontend_connections')::int as ws_connections,
       (m.metadata->>'sse_connections')::int as sse_connections,
       m.metadata->>'connection_quality' as quality,
       m.metadata->>'last_ws_connection' as last_connection
FROM session.active_sessions s
JOIN session.session_metadata m ON s.session_id = m.session_id
WHERE s.expires_at > NOW();
```

## Data Integrity Constraints

1. Session IDs are unique and serve as primary keys
2. Session metadata has a 1:1 relationship with sessions
3. Foreign key constraints enforce relationships
4. Cascade delete ensures clean removal of related records
5. Session expiration is enforced by timestamp fields

_Note: The database schema is created by the initialization job when the Kubernetes cluster is first set up, not by the session service itself._