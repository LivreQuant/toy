-- db/schemas/reconciliation/cash_recon.sql
-- Cash reconciliation tables

CREATE TABLE IF NOT EXISTS reconciliation.cash_balances (
    balance_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    balance_date DATE NOT NULL,
    account_id VARCHAR(50) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    balance_type VARCHAR(50) NOT NULL,
    balance_amount DECIMAL(20,2) NOT NULL,
    source_system VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(balance_date, account_id, currency, balance_type, source_system)
);

CREATE TABLE IF NOT EXISTS reconciliation.cash_movements (
    movement_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    movement_date DATE NOT NULL,
    account_id VARCHAR(50) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    movement_type VARCHAR(50) NOT NULL,
    movement_amount DECIMAL(20,2) NOT NULL,
    reference_id VARCHAR(100),
    description TEXT,
    source_system VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reconciliation.cash_recon (
    recon_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recon_date DATE NOT NULL,
    account_id VARCHAR(50) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    balance_type VARCHAR(50) NOT NULL,
    source_balance DECIMAL(20,2),
    target_balance DECIMAL(20,2),
    balance_difference DECIMAL(20,2),
    reconciliation_status VARCHAR(20) NOT NULL,
    tolerance_breached BOOLEAN DEFAULT FALSE,
    comments TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);