-- Create a new file: schemas/simulator_sessions.sql

CREATE SCHEMA IF NOT EXISTS simulator;

CREATE TABLE IF NOT EXISTS simulator.instances (
    simulator_id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES session.active_sessions(session_id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL CHECK (status IN ('STARTING', 'RUNNING', 'STOPPING', 'STOPPED', 'ERROR')),
    endpoint VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    pod_name VARCHAR(100),
    CONSTRAINT simulator_instances_unique_session UNIQUE (session_id)
);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_simulator_instances_session_id ON simulator.instances(session_id);
CREATE INDEX IF NOT EXISTS idx_simulator_instances_status ON simulator.instances(status);