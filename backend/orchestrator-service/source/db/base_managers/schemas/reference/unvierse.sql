-- db/schemas/reference/universe.sql
-- Trading universe tables

CREATE TABLE IF NOT EXISTS universe.trading_universe (
    universe_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    universe_date DATE NOT NULL,
    is_tradeable BOOLEAN DEFAULT TRUE,
    market_cap DECIMAL(20,2),
    sector VARCHAR(100),
    liquidity_score DECIMAL(5,2),
    inclusion_reason VARCHAR(200),
    exclusion_reason VARCHAR(200),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(symbol, universe_date)
);

CREATE TABLE IF NOT EXISTS universe.universe_rules (
    rule_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rule_name VARCHAR(100) NOT NULL UNIQUE,
    rule_type VARCHAR(50) NOT NULL,
    rule_criteria JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS universe.universe_changes (
    change_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    change_date DATE NOT NULL,
    change_type VARCHAR(20) NOT NULL CHECK (change_type IN ('ADDED', 'REMOVED', 'SUSPENDED')),
    reason TEXT,
    effective_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE universe.trading_universe IS 'Securities eligible for trading';
COMMENT ON TABLE universe.universe_rules IS 'Rules for universe construction';
COMMENT ON TABLE universe.universe_changes IS 'Historical universe changes';