-- Users Schema
CREATE SCHEMA IF NOT EXISTS auth;

CREATE TABLE IF NOT EXISTS auth.users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    role VARCHAR(20) DEFAULT 'user' CHECK (role IN ('admin', 'user', 'demo'))
);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_users_username ON auth.users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON auth.users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON auth.users(role);

-- User preferences table for app settings
CREATE TABLE IF NOT EXISTS auth.user_preferences (
    user_id INTEGER PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    theme VARCHAR(20) DEFAULT 'light',
    default_simulator_config JSONB,
    last_modified TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- API tokens for programmatic access
CREATE TABLE IF NOT EXISTS auth.api_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    description VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_api_tokens_user_id ON auth.api_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_api_tokens_token_hash ON auth.api_tokens(token_hash);

-- Function to hash passwords
CREATE OR REPLACE FUNCTION auth.hash_password(password TEXT)
RETURNS TEXT AS $$
BEGIN
    -- In production, use a proper password hashing library
    -- This is a simple hash for demo purposes only
    RETURN encode(digest(password || 'trading-simulator-salt', 'sha256'), 'hex');
END;
$$ LANGUAGE plpgsql;

-- Function to verify passwords
CREATE OR REPLACE FUNCTION auth.verify_password(
    input_username TEXT,
    input_password TEXT
) RETURNS TABLE (
    user_id INTEGER,
    username VARCHAR(50),
    role VARCHAR(20)
) AS $$
BEGIN
    RETURN QUERY
    SELECT u.id, u.username, u.role
    FROM auth.users u
    WHERE u.username = input_username
    AND u.password_hash = auth.hash_password(input_password)
    AND u.is_active = TRUE;
    
    -- Update last login time if user found
    UPDATE auth.users
    SET last_login = CURRENT_TIMESTAMP
    WHERE username = input_username
    AND password_hash = auth.hash_password(input_password)
    AND is_active = TRUE;
END;
$$ LANGUAGE plpgsql;