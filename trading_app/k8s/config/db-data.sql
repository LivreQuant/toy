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

-- Create authentication helper functions
-- Function to create a new user
CREATE OR REPLACE FUNCTION auth.create_user(
    p_username VARCHAR(50),
    p_email VARCHAR(100),
    p_password TEXT,
    p_first_name VARCHAR(50),
    p_last_name VARCHAR(50),
    p_user_role VARCHAR(20) DEFAULT 'user'
) RETURNS INTEGER AS $$
DECLARE
    new_user_id INTEGER;
BEGIN
    INSERT INTO auth.users (
        username,
        email,
        password_hash,
        first_name,
        last_name,
        user_role
    ) VALUES (
        p_username,
        p_email,
        auth.hash_password(p_password),
        p_first_name,
        p_last_name,
        p_user_role
    )
    RETURNING id INTO new_user_id;
    
    -- Create default preferences
    INSERT INTO auth.user_preferences (
        user_id,
        theme,
        default_simulator_config
    ) VALUES (
        new_user_id,
        'light',
        '{"market_data_refresh_rate": 1000, "default_symbols": ["AAPL", "MSFT", "GOOGL", "AMZN"]}'::jsonb
    );
    
    RETURN new_user_id;
END;
$$ LANGUAGE plpgsql;

-- Function to authenticate a user and return a JWT payload
CREATE OR REPLACE FUNCTION auth.authenticate_user(
    p_username VARCHAR(50),
    p_password TEXT
) RETURNS JSONB AS $$
DECLARE
    result JSONB;
BEGIN
    SELECT jsonb_build_object(
        'user_id', u.id,
        'username', u.username,
        'user_role', u.user_role,
        'authenticated', TRUE
    ) INTO result
    FROM auth.users u
    WHERE u.username = p_username
    AND u.password_hash = auth.hash_password(p_password)
    AND u.is_active = TRUE;
    
    IF result IS NULL THEN
        RETURN jsonb_build_object(
            'authenticated', FALSE,
            'error', 'Invalid username or password'
        );
    END IF;
    
    -- Update last login time
    UPDATE auth.users
    SET last_login = CURRENT_TIMESTAMP
    WHERE username = p_username;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Insert test users with hashed passwords
INSERT INTO auth.users (
    username,
    email,
    password_hash,
    first_name,
    last_name,
    user_role,
    is_active
) VALUES
(
    'testuser',
    'testuser@example.com',
    crypt('password123', gen_salt('bf')),
    'Test',
    'User',
    'user',
    TRUE
)
ON CONFLICT (username) DO NOTHING;