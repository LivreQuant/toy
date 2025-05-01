-- PostgreSQL Extensions
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Users Schema
CREATE SCHEMA IF NOT EXISTS auth;

CREATE TABLE IF NOT EXISTS auth.users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    email_verified BOOLEAN DEFAULT TRUE,
    verification_code VARCHAR(255),
    verification_sent_at TIMESTAMP WITH TIME ZONE,
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

-- Session Schema
CREATE SCHEMA IF NOT EXISTS session;

CREATE TABLE IF NOT EXISTS session.active_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    token TEXT
);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON session.active_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON session.active_sessions(expires_at);

-- Create session metadata table
CREATE TABLE IF NOT EXISTS session.session_details (
    session_id VARCHAR(36) PRIMARY KEY REFERENCES session.active_sessions(session_id) ON DELETE CASCADE,
    
    -- Device and connection information
    device_id VARCHAR(64),
    user_agent TEXT,
    ip_address VARCHAR(45),  -- Supports IPv6
    pod_name VARCHAR(255),
    
    -- Status and quality metrics
    connection_quality VARCHAR(20) CHECK (connection_quality IN ('good', 'degraded', 'poor')),
    heartbeat_latency INTEGER,
    missed_heartbeats INTEGER DEFAULT 0,
    reconnect_count INTEGER DEFAULT 0,
            
    -- Timestamps
    last_reconnect TIMESTAMP WITH TIME ZONE,
    last_device_update TIMESTAMP WITH TIME ZONE,
    last_quality_update TIMESTAMP WITH TIME ZONE
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_session_details_device_id ON session.session_details(device_id);

-- Create cleanup function for expired sessions
CREATE OR REPLACE FUNCTION session.cleanup_expired_sessions() 
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM session.active_sessions
    WHERE expires_at < NOW();
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Simulator Schema
CREATE SCHEMA IF NOT EXISTS simulator;

CREATE TABLE IF NOT EXISTS simulator.instances (
    simulator_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES session.active_sessions(session_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL,
    endpoint TEXT,
    exhange_type VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_simulator_session_id ON simulator.instances(session_id);
CREATE INDEX IF NOT EXISTS idx_simulator_user_id ON simulator.instances(user_id);
CREATE INDEX IF NOT EXISTS idx_simulator_status ON simulator.instances(status);

-- Trading Schema
CREATE SCHEMA IF NOT EXISTS trading;

-- Create orders table if not exists
CREATE TABLE IF NOT EXISTS trading.orders (
  id SERIAL PRIMARY KEY,  -- Add this new primary key
  order_id UUID NOT NULL, -- No longer the primary key, but still indexed
  status VARCHAR(20) NOT NULL,
  user_id VARCHAR(100) NOT NULL,
  symbol VARCHAR(20) NOT NULL,
  side VARCHAR(10) NOT NULL,
  quantity NUMERIC(18,8) NOT NULL,
  price NUMERIC(18,8),
  order_type VARCHAR(20) NOT NULL,
  filled_quantity NUMERIC(18,8) NOT NULL DEFAULT 0,
  avg_price NUMERIC(18,8) NOT NULL DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL,
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
  request_id VARCHAR(100),
  error_message TEXT
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_orders_order_id ON trading.orders(order_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON trading.orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON trading.orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON trading.orders(created_at);

-- Market Data Schema for Minute Bars
CREATE SCHEMA IF NOT EXISTS marketdata;

-- Create market data table for storing minute bars
CREATE TABLE IF NOT EXISTS marketdata.market_data (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timestamp BIGINT NOT NULL,
    open NUMERIC(18, 8) NOT NULL,
    high NUMERIC(18, 8) NOT NULL,
    low NUMERIC(18, 8) NOT NULL,
    close NUMERIC(18, 8) NOT NULL,
    volume INTEGER NOT NULL,
    trade_count INTEGER,
    vwap NUMERIC(18, 8),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_market_data_symbol ON marketdata.market_data(symbol);
CREATE INDEX IF NOT EXISTS idx_market_data_timestamp ON marketdata.market_data(timestamp);
CREATE INDEX IF NOT EXISTS idx_market_data_symbol_timestamp ON marketdata.market_data(symbol, timestamp);

-- Create time-based partitioning function (optional but recommended for production)
CREATE OR REPLACE FUNCTION marketdata.create_partition_for_date(date_val DATE)
RETURNS VOID AS $$
DECLARE
    partition_name TEXT;
BEGIN
    partition_name := 'market_data_' || to_char(date_val, 'YYYY_MM_DD');
    
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS marketdata.%I
        (
            CONSTRAINT %I_pkey PRIMARY KEY (id),
            CONSTRAINT %I_date_check CHECK (timestamp >= %s AND timestamp < %s)
        ) INHERITS (marketdata.market_data);
    ', 
    partition_name, 
    partition_name, 
    partition_name,
    quote_literal(extract(epoch from date_val) * 1000),
    quote_literal(extract(epoch from (date_val + interval '1 day')) * 1000));
    
    -- Create indexes on the partition
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_%I_symbol ON marketdata.%I(symbol);
        CREATE INDEX IF NOT EXISTS idx_%I_timestamp ON marketdata.%I(timestamp);
    ', 
    partition_name, partition_name,
    partition_name, partition_name);
END;
$$ LANGUAGE plpgsql;

-- Create function to ensure the right partition exists for a given timestamp
CREATE OR REPLACE FUNCTION marketdata.insert_market_data_trigger()
RETURNS TRIGGER AS $$
DECLARE
    partition_date DATE;
    partition_name TEXT;
BEGIN
    -- Convert timestamp (in milliseconds) to date
    partition_date := to_timestamp(NEW.timestamp / 1000)::date;
    partition_name := 'market_data_' || to_char(partition_date, 'YYYY_MM_DD');
    
    -- Create partition if it doesn't exist
    PERFORM marketdata.create_partition_for_date(partition_date);
    
    -- Insert into the partition
    EXECUTE format('
        INSERT INTO marketdata.%I (
            symbol, timestamp, open, high, low, close, 
            volume, trade_count, vwap, created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
    ', partition_name)
    USING NEW.symbol, NEW.timestamp, NEW.open, NEW.high, NEW.low, NEW.close,
          NEW.volume, NEW.trade_count, NEW.vwap, NEW.created_at;
    
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger
CREATE TRIGGER insert_market_data_trigger
    BEFORE INSERT ON marketdata.market_data
    FOR EACH ROW EXECUTE FUNCTION marketdata.insert_market_data_trigger();

-- Grant permissions
GRANT USAGE ON SCHEMA marketdata TO opentp;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA marketdata TO opentp;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA marketdata TO opentp;
ALTER DEFAULT PRIVILEGES IN SCHEMA marketdata GRANT ALL ON TABLES TO opentp;
ALTER DEFAULT PRIVILEGES IN SCHEMA marketdata GRANT ALL ON SEQUENCES TO opentp;