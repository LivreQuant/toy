CREATE TABLE IF NOT EXISTS auth.refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE,
    CONSTRAINT unique_token UNIQUE (token_hash)
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_refresh_token_hash ON auth.refresh_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_refresh_token_user_id ON auth.refresh_tokens(user_id);

-- Create cleanup function
CREATE OR REPLACE FUNCTION auth.cleanup_expired_tokens()
RETURNS void AS $$
BEGIN
    DELETE FROM auth.refresh_tokens 
    WHERE expires_at < NOW() OR is_revoked = TRUE;
END;
$$ LANGUAGE plpgsql;