-- db/schemas/reference/exchanges.sql
-- Exchange and market information

CREATE TABLE IF NOT EXISTS reference_data.exchanges (
    exchange_id VARCHAR(20) PRIMARY KEY,
    exchange_name VARCHAR(100) NOT NULL,
    country VARCHAR(3) NOT NULL,
    timezone VARCHAR(50) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    market_open TIME NOT NULL,
    market_close TIME NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Market holidays
CREATE TABLE IF NOT EXISTS reference_data.market_holidays (
    holiday_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    exchange_id VARCHAR(20) REFERENCES reference_data.exchanges(exchange_id),
    holiday_date DATE NOT NULL,
    holiday_name VARCHAR(200) NOT NULL,
    is_full_day BOOLEAN DEFAULT TRUE,
    partial_open TIME,
    partial_close TIME,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_exchange_holiday UNIQUE(exchange_id, holiday_date)
);

-- Exchange metadata for orchestrator
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
    namespace VARCHAR(50),
    last_snap TIMESTAMP WITH TIME ZONE,
    updated_time TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE reference_data.exchanges IS 'Exchange master data with trading hours';
COMMENT ON TABLE reference_data.market_holidays IS 'Market holidays and partial trading days';
COMMENT ON TABLE exch_us_equity.metadata IS 'Exchange service metadata for orchestrator';