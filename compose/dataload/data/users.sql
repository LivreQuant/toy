-- Insert test users with hashed passwords
INSERT INTO auth.users (
    username,
    email,
    password_hash,
    first_name,
    last_name,
    role,
    is_active
) VALUES
(
    'testuser',
    'testuser@example.com',
    auth.hash_password('password123'),
    'Test',
    'User',
    'user',
    TRUE
),
(
    'admin',
    'admin@example.com',
    auth.hash_password('admin123'),
    'Admin',
    'User',
    'admin',
    TRUE
),
(
    'demo',
    'demo@example.com',
    auth.hash_password('demo123'),
    'Demo',
    'User',
    'demo',
    TRUE
)
ON CONFLICT (username) DO NOTHING;

-- Insert default preferences for users
INSERT INTO auth.user_preferences (
    user_id,
    theme,
    default_simulator_config
) 
SELECT 
    id,
    'dark',
    '{"market_data_refresh_rate": 1000, "default_symbols": ["AAPL", "MSFT", "GOOGL", "AMZN"]}'::jsonb
FROM auth.users
WHERE username = 'testuser'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO auth.user_preferences (
    user_id,
    theme,
    default_simulator_config
) 
SELECT 
    id,
    'light',
    '{"market_data_refresh_rate": 500, "default_symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META"]}'::jsonb
FROM auth.users
WHERE username = 'admin'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO auth.user_preferences (
    user_id,
    theme,
    default_simulator_config
) 
SELECT 
    id,
    'light',
    '{"market_data_refresh_rate": 2000, "default_symbols": ["AAPL", "MSFT"]}'::jsonb
FROM auth.users
WHERE username = 'demo'
ON CONFLICT (user_id) DO NOTHING;