-- Make sure you're not connected to opentp database
\c postgres

-- Force terminate ALL connections to opentp database
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'opentp';

-- Drop the database (should work now)
DROP DATABASE IF EXISTS opentp;

-- Drop the role (we'll recreate it)
DROP ROLE IF EXISTS opentp;

-- Now create everything from scratch
CREATE DATABASE opentp;
CREATE ROLE opentp LOGIN PASSWORD 'samaral';
GRANT ALL PRIVILEGES ON DATABASE opentp TO opentp;

-- Connect to the new database
\c opentp

-- Create user if not exists (adjust password as needed)
DO
$do$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'opentp') THEN
      CREATE ROLE opentp LOGIN PASSWORD 'samaral';
   END IF;
END
$do$;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE opentp TO opentp;

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
    user_role VARCHAR(20) DEFAULT 'user' CHECK (user_role IN ('admin', 'user', 'demo'))
);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_users_username ON auth.users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON auth.users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON auth.users(user_role);

-- User preferences table for app settings
CREATE TABLE IF NOT EXISTS auth.user_preferences (
    user_id INTEGER PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    theme VARCHAR(20) DEFAULT 'light',
    default_simulator_config JSONB,
    last_modified TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create the pgcrypto extension if not exists
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Function to hash passwords
CREATE OR REPLACE FUNCTION auth.hash_password(password TEXT)
RETURNS TEXT AS $$
BEGIN
    RETURN encode(digest(password || 'trading-simulator-salt', 'sha256'), 'hex');
END;
$$ LANGUAGE plpgsql;

-- Token management
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

-- Function to verify user password (non-ambiguous version)
CREATE OR REPLACE FUNCTION auth.verify_password(
    p_username VARCHAR,
    p_password VARCHAR
) RETURNS TABLE(user_id INTEGER, user_role VARCHAR) AS $$
DECLARE
    user_record RECORD;
BEGIN
    -- Get user with table alias to avoid ambiguity
    SELECT u.id, u.password_hash, u.user_role INTO user_record
    FROM auth.users u
    WHERE u.username = p_username AND u.is_active = TRUE;

    -- Simple password check
    IF user_record IS NOT NULL AND
       user_record.password_hash = crypt(p_password, user_record.password_hash) THEN
        -- Return user info
        user_id := user_record.id;
        user_role := user_record.user_role;
        RETURN NEXT;

        -- Update last login
        UPDATE auth.users SET last_login = NOW()
        WHERE id = user_record.id;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
EOF

-- Insert test user with properly hashed password
INSERT INTO auth.users (
    username,
    email,
    password_hash,
    first_name,
    last_name,
    user_role,
    is_active
) VALUES (
    'testuser',
    'testuser@example.com',
    crypt('password123', gen_salt('bf')),
    'Test',
    'User',
    'user',
    TRUE
)
ON CONFLICT (username) DO NOTHING;

-- Connect to your database as postgres user
\c opentp postgres

-- Grant permissions to the opentp user on the auth schema
GRANT USAGE ON SCHEMA auth TO opentp;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA auth TO opentp;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA auth TO opentp;

-- Make sure future tables get the same permissions
ALTER DEFAULT PRIVILEGES IN SCHEMA auth GRANT ALL ON TABLES TO opentp;
ALTER DEFAULT PRIVILEGES IN SCHEMA auth GRANT ALL ON SEQUENCES TO opentp;