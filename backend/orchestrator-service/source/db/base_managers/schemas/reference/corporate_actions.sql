-- db/schemas/reference/corporate_actions.sql
-- Corporate actions processing tables

CREATE TABLE IF NOT EXISTS corporate_actions.actions (
    action_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    action_type VARCHAR(50) NOT NULL CHECK (action_type IN ('DIVIDEND', 'STOCK_SPLIT', 'STOCK_DIVIDEND', 'SPINOFF', 'MERGER', 'RIGHTS')),
    ex_date DATE NOT NULL,
    record_date DATE,
    pay_date DATE,
    amount DECIMAL(20,8),
    ratio DECIMAL(20,8),
    new_symbol VARCHAR(20),
    description TEXT,
    status VARCHAR(20) DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PROCESSED', 'CANCELLED')),
    source VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS corporate_actions.price_adjustment_history (
    adjustment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    adjustment_date DATE NOT NULL,
    adjustment_type VARCHAR(50) NOT NULL,
    old_price DECIMAL(20,8),
    new_price DECIMAL(20,8),
    adjustment_factor DECIMAL(20,8),
    dividend_amount DECIMAL(20,8) DEFAULT 0,
    split_ratio DECIMAL(20,8) DEFAULT 1,
    adjustment_reason TEXT,
    status VARCHAR(20) DEFAULT 'APPLIED',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS corporate_actions.position_adjustment_audit (
    audit_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    adjustment_date DATE NOT NULL,
    adjustment_type VARCHAR(50) NOT NULL,
    old_quantity DECIMAL(20,8),
    new_quantity DECIMAL(20,8),
    old_avg_cost DECIMAL(20,8),
    new_avg_cost DECIMAL(20,8),
    cash_impact DECIMAL(20,2) DEFAULT 0,
    corporate_action_id UUID REFERENCES corporate_actions.actions(action_id),
    status VARCHAR(20) DEFAULT 'APPLIED',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE corporate_actions.actions IS 'Corporate action events requiring processing';
COMMENT ON TABLE corporate_actions.price_adjustment_history IS 'Historical price adjustments from corporate actions';
COMMENT ON TABLE corporate_actions.position_adjustment_audit IS 'Position adjustments audit trail';