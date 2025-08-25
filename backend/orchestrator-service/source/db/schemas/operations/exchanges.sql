-- db/schemas/operations/exchanges.sql
-- Exchange operations and metadata tables

-- Exchange service metadata (for orchestrator)
CREATE TABLE IF NOT EXISTS exch_us_equity.metadata (
    exch_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    exchange_type VARCHAR(50) NOT NULL,
    exchanges TEXT[] NOT NULL,
    timezone VARCHAR(50) NOT NULL,
    pre_market_open TIME NOT NULL,
    market_open TIME NOT NULL,
    market_close TIME NOT NULL,
    post_market_close TIME NOT NULL,
    endpoint VARCHAR(200),
    pod_name VARCHAR(100),
    namespace VARCHAR(50) DEFAULT 'default',
    last_snap TIMESTAMP WITH TIME ZONE,
    updated_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_market_hours_order CHECK (
        pre_market_open < market_open AND 
        market_open < market_close AND 
        market_close < post_market_close
    )
);

-- Exchange session tracking
CREATE TABLE IF NOT EXISTS exch_us_equity.session_tracking (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    exch_id UUID REFERENCES exch_us_equity.metadata(exch_id),
    session_date DATE NOT NULL,
    session_type VARCHAR(20) NOT NULL CHECK (session_type IN ('PRE_MARKET', 'REGULAR', 'POST_MARKET')),
    session_start_time TIMESTAMP WITH TIME ZONE,
    session_end_time TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'SCHEDULED' CHECK (status IN ('SCHEDULED', 'OPEN', 'CLOSED', 'SUSPENDED', 'CANCELLED')),
    messages_processed BIGINT DEFAULT 0,
    last_activity TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_exchange_session UNIQUE(exch_id, session_date, session_type)
);

-- Exchange connectivity status
CREATE TABLE IF NOT EXISTS exch_us_equity.connectivity_status (
    status_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    exch_id UUID REFERENCES exch_us_equity.metadata(exch_id),
    connection_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('CONNECTED', 'DISCONNECTED', 'CONNECTING', 'ERROR')),
    last_heartbeat TIMESTAMP WITH TIME ZONE,
    latency_ms INTEGER,
    error_message TEXT,
    reconnect_attempts INTEGER DEFAULT 0,
    status_changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Exchange performance metrics
CREATE TABLE IF NOT EXISTS exch_us_equity.performance_metrics (
    metric_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    exch_id UUID REFERENCES exch_us_equity.metadata(exch_id),
    metric_date DATE NOT NULL,
    metric_hour INTEGER NOT NULL CHECK (metric_hour BETWEEN 0 AND 23),
    messages_received BIGINT DEFAULT 0,
    messages_processed BIGINT DEFAULT 0,
    messages_rejected BIGINT DEFAULT 0,
    avg_latency_ms DECIMAL(8,2),
    max_latency_ms INTEGER,
    error_count INTEGER DEFAULT 0,
    uptime_percentage DECIMAL(5,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_exchange_metrics UNIQUE(exch_id, metric_date, metric_hour)
);

-- Market data quality tracking
CREATE TABLE IF NOT EXISTS exch_us_equity.data_quality_metrics (
    quality_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    exch_id UUID REFERENCES exch_us_equity.metadata(exch_id),
    symbol VARCHAR(20) NOT NULL,
    metric_date DATE NOT NULL,
    total_quotes BIGINT DEFAULT 0,
    stale_quotes INTEGER DEFAULT 0,
    crossed_quotes INTEGER DEFAULT 0,
    wide_spreads INTEGER DEFAULT 0,
    zero_bids INTEGER DEFAULT 0,
    zero_offers INTEGER DEFAULT 0,
    quality_score DECIMAL(5,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_data_quality UNIQUE(exch_id, symbol, metric_date)
);

-- Exchange configuration history
CREATE TABLE IF NOT EXISTS exch_us_equity.configuration_history (
    config_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    exch_id UUID REFERENCES exch_us_equity.metadata(exch_id),
    config_key VARCHAR(100) NOT NULL,
    old_value TEXT,
    new_value TEXT NOT NULL,
    change_reason TEXT,
    changed_by VARCHAR(100) NOT NULL,
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Exchange alerts and incidents
CREATE TABLE IF NOT EXISTS exch_us_equity.exchange_alerts (
    alert_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    exch_id UUID REFERENCES exch_us_equity.metadata(exch_id),
    alert_type VARCHAR(50) NOT NULL,
    alert_level VARCHAR(20) NOT NULL CHECK (alert_level IN ('INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    alert_message TEXT NOT NULL,
    alert_data JSONB,
    is_resolved BOOLEAN DEFAULT FALSE,
    resolved_by VARCHAR(100),
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Market status tracking
CREATE TABLE IF NOT EXISTS exch_us_equity.market_status (
    status_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    exch_id UUID REFERENCES exch_us_equity.metadata(exch_id),
    status_date DATE NOT NULL,
    market_status VARCHAR(20) NOT NULL CHECK (market_status IN ('CLOSED', 'PRE_OPEN', 'OPEN', 'POST_CLOSE', 'SUSPENDED', 'HOLIDAY')),
    status_reason VARCHAR(200),
    effective_time TIMESTAMP WITH TIME ZONE NOT NULL,
    next_status VARCHAR(20),
    next_status_time TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Comments
COMMENT ON TABLE exch_us_equity.metadata IS 'Exchange service configuration and metadata';
COMMENT ON TABLE exch_us_equity.session_tracking IS 'Daily trading session tracking';
COMMENT ON TABLE exch_us_equity.connectivity_status IS 'Real-time exchange connectivity status';
COMMENT ON TABLE exch_us_equity.performance_metrics IS 'Exchange performance metrics by hour';
COMMENT ON TABLE exch