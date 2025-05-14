# Authorization Service Database Requirements

This document outlines the PostgreSQL database requirements for the Authorization Service.

## Schema Structure

The service requires a PostgreSQL database with the following schema:

### Schemas

- `auth` - Main schema for authentication and authorization data

### Tables

#### `auth.users`

Stores user account information.

```sql
CREATE TABLE auth.users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(200) NOT NULL,
    email VARCHAR(200),
    user_role VARCHAR(50) DEFAULT 'user',  -- Renamed from 'role' to avoid ambiguity
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE
);
```

#### `auth.refresh_tokens`

Stores refresh tokens for JWT authentication.

```sql
CREATE TABLE auth.refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE,
    CONSTRAINT unique_token UNIQUE (token_hash)
);
```

### Functions

#### `auth.verify_password`

Function to verify user passwords and update last login time.

```sql
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
    
    -- Password check
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
```

#### `auth.cleanup_expired_tokens`

Function to clean up expired or revoked refresh tokens.

```sql
CREATE OR REPLACE FUNCTION auth.cleanup_expired_tokens()
RETURNS void AS $$
BEGIN
    DELETE FROM auth.refresh_tokens 
    WHERE expires_at < NOW() OR is_revoked = TRUE;
END;
$$ LANGUAGE plpgsql;
```

### Extensions

- `pgcrypto` - Required for password hashing functions

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

## Default Users

For development, a test user should be created:

```sql
INSERT INTO auth.users (
    username,
    password_hash,
    email,
    user_role,
    is_active
) VALUES (
    'testuser',
    crypt('password123', gen_salt('bf')),
    'testuser@example.com',
    'user',
    TRUE
) ON CONFLICT (username) DO NOTHING;
```

## Database Connection

The service connects to PostgreSQL using the following environment variables:

- `DB_HOST` - Database hostname (default: 'localhost')
- `DB_PORT` - Database port (default: '5432')
- `DB_NAME` - Database name (default: 'opentp')
- `DB_USER` - Database username (default: 'opentp')
- `DB_PASSWORD` - Database password (default: 'samaral')
- `DB_MIN_CONNECTIONS` - Minimum connections (default: 1)
- `DB_MAX_CONNECTIONS` - Maximum connections (default: 10)

## Database Initialization

Database initialization should be performed via Kubernetes initialization jobs, not by the service itself. The service expects the database to be ready with all required schemas, tables, and functions already created.