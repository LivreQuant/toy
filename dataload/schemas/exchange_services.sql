-- exchange_services.sql

-- Create table to track exchange services
CREATE TABLE IF NOT EXISTS session.exchange_services (
    exchange_id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES session.active_sessions(session_id) ON DELETE CASCADE,
    endpoint VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    inactivity_timeout_seconds INTEGER DEFAULT 300,
    CONSTRAINT unique_session_exchange UNIQUE (session_id)
);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_exchange_services_session_id ON session.exchange_services(session_id);
CREATE INDEX IF NOT EXISTS idx_exchange_services_last_active ON session.exchange_services(last_active);

-- Add function to clean up inactive exchange services
CREATE OR REPLACE FUNCTION session.cleanup_inactive_exchange_services() RETURNS void AS $$
DECLARE
    exchange record;
BEGIN
    FOR exchange IN 
        SELECT 
            es.exchange_id, 
            es.session_id,
            es.last_active,
            es.inactivity_timeout_seconds
        FROM 
            session.exchange_services es
        WHERE
            es.last_active < NOW() - (es.inactivity_timeout_seconds * interval '1 second')
   LOOP
       -- Mark exchange for cleanup in simulator.instances table if it exists
       UPDATE simulator.instances
       SET status = 'STOPPING'
       WHERE simulator_id = exchange.exchange_id;
       
       -- Remove the exchange service record
       DELETE FROM session.exchange_services
       WHERE exchange_id = exchange.exchange_id;
       
       -- Update session metadata to clear simulator info
       UPDATE session.session_metadata
       SET metadata = jsonb_set(
           metadata::jsonb,
           '{simulator_id}',
           'null'::jsonb
       )
       WHERE session_id = exchange.session_id;
       
       UPDATE session.session_metadata
       SET metadata = jsonb_set(
           metadata::jsonb,
           '{simulator_endpoint}',
           'null'::jsonb
       )
       WHERE session_id = exchange.session_id;
   END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Modify existing session cleanup function to also clean up exchange services
CREATE OR REPLACE FUNCTION session.cleanup_expired_sessions() RETURNS void AS $$
BEGIN
   -- First clean up exchange services for expired sessions
   DELETE FROM session.exchange_services
   WHERE session_id IN (
       SELECT session_id 
       FROM session.active_sessions 
       WHERE expires_at < NOW()
   );
   
   -- Then clean up simulator instances
   UPDATE simulator.instances
   SET status = 'STOPPING'
   WHERE session_id IN (
       SELECT session_id 
       FROM session.active_sessions 
       WHERE expires_at < NOW()
   );
   
   -- Finally remove expired sessions
   DELETE FROM session.active_sessions 
   WHERE expires_at < NOW();
   
   -- Call the exchange service cleanup to handle inactive exchanges
   PERFORM session.cleanup_inactive_exchange_services();
END;
$$ LANGUAGE plpgsql;