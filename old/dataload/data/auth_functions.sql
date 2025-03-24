-- Create authentication helper functions

-- Function to create a new user
CREATE OR REPLACE FUNCTION auth.create_user(
    p_username VARCHAR(50),
    p_email VARCHAR(100),
    p_password TEXT,
    p_first_name VARCHAR(50),
    p_last_name VARCHAR(50),
    p_role VARCHAR(20) DEFAULT 'user'
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
        role
    ) VALUES (
        p_username,
        p_email,
        auth.hash_password(p_password),
        p_first_name,
        p_last_name,
        p_role
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
        'role', u.role,
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