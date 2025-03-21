-- Create a new file: schemas/sessions.sql

CREATE SCHEMA IF NOT EXISTS session;

CREATE TABLE IF NOT EXISTS session.active_sessions (
    session_id UUID PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    CONSTRAINT active_sessions_unique_user UNIQUE (user_id)
);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_active_sessions_user_id ON session.active_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_active_sessions_token ON session.active_sessions(token);
CREATE INDEX IF NOT EXISTS idx_active_sessions_expires_at ON session.active_sessions(expires_at);