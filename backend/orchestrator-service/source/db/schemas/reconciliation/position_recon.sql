-- db/schemas/reconciliation/position_recon.sql
-- Position reconciliation tables

CREATE TABLE IF NOT EXISTS reconciliation.position_recon (
    recon_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recon_date DATE NOT NULL,
    account_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    source_system VARCHAR(50) NOT NULL,
    target_system VARCHAR(50) NOT NULL,
    source_quantity DECIMAL(20,8),
    target_quantity DECIMAL(20,8),
    quantity_difference DECIMAL(20,8),
    source_market_value DECIMAL(20,2),
    target_market_value DECIMAL(20,2),
    value_difference DECIMAL(20,2),
    reconciliation_status VARCHAR(20) NOT NULL,
    tolerance_breached BOOLEAN DEFAULT FALSE,
    comments TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reconciliation.recon_summary (
    summary_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recon_date DATE NOT NULL,
    total_positions INTEGER NOT NULL,
    matched_positions INTEGER NOT NULL,
    discrepancy_positions INTEGER NOT NULL,
    missing_positions INTEGER NOT NULL,
    total_market_value DECIMAL(20,2),
    total_discrepancy_value DECIMAL(20,2),
    reconciliation_rate DECIMAL(8,4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);