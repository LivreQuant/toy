-- db/schemas/core/pnl.sql
-- P&L and performance measurement tables

-- Daily P&L calculations
CREATE TABLE IF NOT EXISTS pnl.daily_pnl (
    pnl_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20), -- NULL for portfolio-level P&L
    pnl_date DATE NOT NULL,
    
    -- P&L components
    realized_pnl DECIMAL(20,2) NOT NULL DEFAULT 0,
    unrealized_pnl DECIMAL(20,2) NOT NULL DEFAULT 0,
    total_pnl DECIMAL(20,2) NOT NULL DEFAULT 0,
    
    -- Position values
    market_value_start DECIMAL(20,2) NOT NULL DEFAULT 0,
    market_value_end DECIMAL(20,2) NOT NULL DEFAULT 0,
    quantity_start DECIMAL(20,8) NOT NULL DEFAULT 0,
    quantity_end DECIMAL(20,8) NOT NULL DEFAULT 0,
    
    -- P&L attribution
    trading_pnl DECIMAL(20,2) NOT NULL DEFAULT 0,
    price_pnl DECIMAL(20,2) NOT NULL DEFAULT 0,
    fx_pnl DECIMAL(20,2) NOT NULL DEFAULT 0,
    dividends DECIMAL(20,2) NOT NULL DEFAULT 0,
    interest DECIMAL(20,2) NOT NULL DEFAULT 0,
    fees DECIMAL(20,2) NOT NULL DEFAULT 0,
    
    -- Calculated fields
    day_change_pct DECIMAL(8,4),
    contribution_to_portfolio DECIMAL(8,4),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_daily_pnl_account_symbol_date UNIQUE(account_id, COALESCE(symbol, ''), pnl_date),
    CONSTRAINT chk_daily_pnl_total_equals_components CHECK (
        ABS(total_pnl - (realized_pnl + unrealized_pnl)) < 0.01
    )
);

-- Portfolio performance metrics
CREATE TABLE IF NOT EXISTS pnl.portfolio_performance (
    performance_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(50) NOT NULL,
    performance_date DATE NOT NULL,
    
    -- Returns
    total_return_pct DECIMAL(12,6) NOT NULL,
    benchmark_return_pct DECIMAL(12,6),
    excess_return_pct DECIMAL(12,6),
    
    -- Risk metrics
    volatility_pct DECIMAL(12,6),
    sharpe_ratio DECIMAL(12,6),
    sortino_ratio DECIMAL(12,6),
    max_drawdown_pct DECIMAL(12,6),
    beta DECIMAL(8,4),
    alpha_pct DECIMAL(12,6),
    
    -- Portfolio values
    portfolio_value DECIMAL(20,2) NOT NULL,
    cash_balance DECIMAL(20,2) NOT NULL DEFAULT 0,
    leverage_ratio DECIMAL(8,4),
    
    -- Performance attribution
    asset_allocation_effect DECIMAL(12,6),
    security_selection_effect DECIMAL(12,6),
    interaction_effect DECIMAL(12,6),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_portfolio_performance_account_date UNIQUE(account_id, performance_date)
);

-- Performance benchmarks
CREATE TABLE IF NOT EXISTS pnl.performance_benchmarks (
    benchmark_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    benchmark_code VARCHAR(20) NOT NULL UNIQUE,
    benchmark_name VARCHAR(200) NOT NULL,
    benchmark_type VARCHAR(50) NOT NULL CHECK (benchmark_type IN ('INDEX', 'CUSTOM', 'PEER_GROUP')),
    currency VARCHAR(3) DEFAULT 'USD',
    provider VARCHAR(100),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Benchmark returns
CREATE TABLE IF NOT EXISTS pnl.benchmark_returns (
    return_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    benchmark_id UUID REFERENCES pnl.performance_benchmarks(benchmark_id),
    return_date DATE NOT NULL,
    return_value DECIMAL(12,8) NOT NULL,
    return_type VARCHAR(20) DEFAULT 'TOTAL' CHECK (return_type IN ('TOTAL', 'PRICE', 'DIVIDEND')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_benchmark_returns UNIQUE(benchmark_id, return_date, return_type)
);

-- P&L explanations and commentary
CREATE TABLE IF NOT EXISTS pnl.pnl_explanations (
    explanation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(50) NOT NULL,
    pnl_date DATE NOT NULL,
    symbol VARCHAR(20),
    explanation_type VARCHAR(50) NOT NULL CHECK (explanation_type IN ('LARGE_MOVE', 'CORPORATE_ACTION', 'TRADE', 'OTHER')),
    explanation TEXT NOT NULL,
    impact_amount DECIMAL(20,2),
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Comments
COMMENT ON TABLE pnl.daily_pnl IS 'Daily P&L calculations by account and security';
COMMENT ON TABLE pnl.portfolio_performance IS 'Portfolio-level performance metrics and attribution';
COMMENT ON TABLE pnl.performance_benchmarks IS 'Benchmark definitions for performance comparison';
COMMENT ON TABLE pnl.benchmark_returns IS 'Historical benchmark return data';
COMMENT ON TABLE pnl.pnl_explanations IS 'Manual explanations for significant P&L movements';