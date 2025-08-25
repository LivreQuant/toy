-- db/schemas/core/trades.sql
-- Trade and settlement related tables

-- Main trades table
CREATE TABLE IF NOT EXISTS settlement.trades (
    trade_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side trade_side NOT NULL,
    quantity DECIMAL(20,8) NOT NULL,
    price DECIMAL(20,8) NOT NULL,
    trade_value DECIMAL(20,2) NOT NULL,
    commission DECIMAL(20,2) NOT NULL DEFAULT 0,
    fees DECIMAL(20,2) NOT NULL DEFAULT 0,
    sec_fees DECIMAL(20,2) NOT NULL DEFAULT 0,
    other_fees DECIMAL(20,2) NOT NULL DEFAULT 0,
    net_amount DECIMAL(20,2) NOT NULL,
    trade_date DATE NOT NULL,
    settlement_date DATE,
    settlement_status settlement_status DEFAULT 'PENDING',
    execution_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    venue VARCHAR(50),
    order_id VARCHAR(100),
    execution_id VARCHAR(100),
    counterparty VARCHAR(100),
    trader_id VARCHAR(50),
    strategy VARCHAR(100),
    trade_type VARCHAR(20) DEFAULT 'NORMAL' CHECK (trade_type IN ('NORMAL', 'OPENING', 'CLOSING', 'CROSS', 'BLOCK')),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_trades_quantity_positive CHECK (quantity > 0),
    CONSTRAINT chk_trades_price_positive CHECK (price > 0),
    CONSTRAINT chk_trades_settlement_date_valid CHECK (settlement_date IS NULL OR settlement_date >= trade_date)
);

-- Settlement instructions table
CREATE TABLE IF NOT EXISTS settlement.settlement_instructions (
    instruction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trade_id UUID REFERENCES settlement.trades(trade_id) ON DELETE CASCADE,
    instruction_type VARCHAR(50) NOT NULL CHECK (instruction_type IN ('DVP', 'FOP', 'CASH', 'REPO')),
    counterparty VARCHAR(100),
    settlement_account VARCHAR(100),
    custodian VARCHAR(100),
    delivery_instructions TEXT,
    special_instructions TEXT,
    status VARCHAR(20) DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'SENT', 'MATCHED', 'SETTLED', 'FAILED')),
    sent_at TIMESTAMP WITH TIME ZONE,
    matched_at TIMESTAMP WITH TIME ZONE,
    settled_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Trade allocations for block trades
CREATE TABLE IF NOT EXISTS settlement.trade_allocations (
    allocation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parent_trade_id UUID REFERENCES settlement.trades(trade_id) ON DELETE CASCADE,
    account_id VARCHAR(50) NOT NULL,
    allocated_quantity DECIMAL(20,8) NOT NULL,
    allocated_amount DECIMAL(20,2) NOT NULL,
    allocation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    status VARCHAR(20) DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'CONFIRMED', 'SETTLED')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Trade corrections and cancellations
CREATE TABLE IF NOT EXISTS settlement.trade_corrections (
    correction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    original_trade_id UUID REFERENCES settlement.trades(trade_id),
    correction_type VARCHAR(20) NOT NULL CHECK (correction_type IN ('CANCEL', 'CORRECT', 'BUST')),
    corrected_trade_id UUID REFERENCES settlement.trades(trade_id),
    reason TEXT NOT NULL,
    authorized_by VARCHAR(100) NOT NULL,
    correction_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Failed trades table
CREATE TABLE IF NOT EXISTS settlement.failed_trades (
    failed_trade_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trade_id UUID REFERENCES settlement.trades(trade_id),
    failure_reason TEXT NOT NULL,
    failure_date DATE NOT NULL,
    resolution_status VARCHAR(20) DEFAULT 'OPEN' CHECK (resolution_status IN ('OPEN', 'INVESTIGATING', 'RESOLVED')),
    assigned_to VARCHAR(100),
    resolution_notes TEXT,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Comments
COMMENT ON TABLE settlement.trades IS 'All trade executions with settlement details';
COMMENT ON TABLE settlement.settlement_instructions IS 'Settlement instructions sent to custodians/clearers';
COMMENT ON TABLE settlement.trade_allocations IS 'Allocation of block trades to individual accounts';
COMMENT ON TABLE settlement.trade_corrections IS 'Trade corrections, cancellations and busts';
COMMENT ON TABLE settlement.failed_trades IS 'Failed settlements requiring investigation';