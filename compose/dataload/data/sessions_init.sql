-- Create a new file: data/sessions_init.sql

-- Create a function to clean up expired sessions
CREATE OR REPLACE FUNCTION session.cleanup_expired_sessions()
RETURNS void AS $$
BEGIN
    -- Remove expired simulators first
    DELETE FROM simulator.instances
    WHERE session_id IN (
        SELECT session_id 
        FROM session.active_sessions 
        WHERE expires_at < NOW()
    );
    
    -- Then remove expired sessions
    DELETE FROM session.active_sessions 
    WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- Create a function to update last_active timestamp
CREATE OR REPLACE FUNCTION session.update_session_activity(p_session_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    session_exists BOOLEAN;
BEGIN
    UPDATE session.active_sessions
    SET last_active = NOW()
    WHERE session_id = p_session_id
    RETURNING TRUE INTO session_exists;
    
    RETURN COALESCE(session_exists, FALSE);
END;
$$ LANGUAGE plpgsql;