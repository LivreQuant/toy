-- Create a new file: schemas/connection_monitoring.sql

CREATE SCHEMA IF NOT EXISTS monitoring;

CREATE TABLE IF NOT EXISTS monitoring.connection_quality (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES session.active_sessions(session_id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    latency_ms INTEGER,
    consecutive_heartbeat_misses INTEGER DEFAULT 0,
    connection_quality VARCHAR(10) CHECK (connection_quality IN ('good', 'degraded', 'poor')),
    CONSTRAINT connection_quality_unique_session_timestamp UNIQUE (session_id, timestamp)
);

-- Keep only recent connection quality records
CREATE INDEX IF NOT EXISTS idx_connection_quality_session_timestamp ON monitoring.connection_quality(session_id, timestamp);