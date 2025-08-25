-- db/schemas/core/positions.sql
-- Position and pricing related tables

-- Current positions table
CREATE TABLE IF NOT EXISTS positions.current_positions (
    position_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    quantity DECIMAL(20,8) NOT NULL DEFAULT 0,
    avg_cost DECIMAL(20,8) NOT NULL DEFAULT 0,
    market_value DECIMAL(20,2) NOT NULL DEFAULT 0,
    unrealized_pnl DECIMAL(20,2) NOT NULL DEFAULT 0,
    last_price DECIMAL(20,8),
    position_date DATE NOT NULL,
    book_cost DECIMAL(20,2) GENERATED ALWAYS AS (quantity * avg_cost) STORED,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_positions_account_symbol_date UNIQUE(account_id, symbol, position_date),
    CONSTRAINT chk_positions_quantity_valid CHECK (quantity IS NOT NULL),
    CONSTRAINT chk_positions_cost_positive CHECK (avg_cost >= 0)
);

-- Position history for point-in-time snapshots
CREATE TABLE IF NOT EXISTS positions.position_history (
    history_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    quantity DECIMAL(20,8) NOT NULL,
    avg_cost DECIMAL(20,8) NOT NULL,
    market_value DECIMAL(20,2) NOT NULL,
    unrealized_pnl DECIMAL(20,2) NOT NULL,
    last_price DECIMAL(20,8),
    position_date DATE NOT NULL,
    snapshot_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    snapshot_type VARCHAR(20) DEFAULT 'EOD' CHECK (snapshot_type IN ('EOD', 'INTRADAY', 'MANUAL')),
    
    CONSTRAINT uk_position_history_unique UNIQUE(account_id, symbol, position_date, snapshot_type)
);

-- EOD prices table
CREATE TABLE IF NOT EXISTS positions.eod_prices (
    price_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    price DECIMAL(20,8) NOT NULL,
    price_date DATE NOT NULL,
    pricing_source VARCHAR(50) DEFAULT 'MARKET' CHECK (pricing_source IN ('MARKET', 'VENDOR', 'MODEL', 'MANUAL')),
    currency VARCHAR(3) DEFAULT 'USD',
    volume BIGINT,
    high_price DECIMAL(20,8),
    low_price DECIMAL(20,8),
    open_price DECIMAL(20,8),
    previous_close DECIMAL(20,8),
    price_change DECIMAL(20,8),
    price_change_pct DECIMAL(8,4),
    quality_flag VARCHAR(10) DEFAULT 'GOOD' CHECK (quality_flag IN ('GOOD', 'STALE', 'SUSPECT', 'MANUAL')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_eod_prices_symbol_date_source UNIQUE(symbol, price_date, pricing_source),
    CONSTRAINT chk_eod_prices_positive CHECK (price > 0)
);

-- Intraday prices for real-time updates
CREATE TABLE IF NOT EXISTS positions.intraday_prices (
    price_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    price DECIMAL(20,8) NOT NULL,
    price_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    pricing_source VARCHAR(50) DEFAULT 'MARKET',
    volume INTEGER,
    bid_price DECIMAL(20,8),
    ask_price DECIMAL(20,8),
    spread DECIMAL(20,8),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Comments on tables
COMMENT ON TABLE positions.current_positions IS 'Current position holdings by account and symbol';
COMMENT ON TABLE positions.position_history IS 'Historical snapshots of positions for audit and analysis';
COMMENT ON TABLE positions.eod_prices IS 'End-of-day prices for all securities';
COMMENT ON TABLE positions.intraday_prices IS 'Intraday price updates for real-time valuation';

-- Comments on key columns
COMMENT ON COLUMN positions.current_positions.book_cost IS 'Calculated as quantity * avg_cost, stored for performance';
COMMENT ON COLUMN positions.eod_prices.quality_flag IS 'Data quality indicator for pricing';