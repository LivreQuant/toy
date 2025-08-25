-- db/schemas/risk/attribution.sql
-- Performance attribution tables

CREATE TABLE IF NOT EXISTS attribution.attribution_analysis (
    analysis_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(50) NOT NULL,
    analysis_date DATE NOT NULL,
    attribution_level VARCHAR(20) NOT NULL,
    attribution_category VARCHAR(100),
    portfolio_weight DECIMAL(8,6) NOT NULL,
    benchmark_weight DECIMAL(8,6) NOT NULL,
    portfolio_return DECIMAL(12,8) NOT NULL,
    benchmark_return DECIMAL(12,8) NOT NULL,
    allocation_effect DECIMAL(12,8) NOT NULL,
    selection_effect DECIMAL(12,8) NOT NULL,
    interaction_effect DECIMAL(12,8) NOT NULL,
    total_effect DECIMAL(12,8) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Risk attribution
CREATE TABLE IF NOT EXISTS attribution.risk_attribution (
    risk_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(50) NOT NULL,
    analysis_date DATE NOT NULL,
    factor_name VARCHAR(100) NOT NULL,
    factor_exposure DECIMAL(12,8) NOT NULL,
    factor_return DECIMAL(12,8) NOT NULL,
    contribution_to_return DECIMAL(12,8) NOT NULL,
    contribution_to_risk DECIMAL(12,8) NOT NULL,
    marginal_contribution DECIMAL(12,8) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Style attribution
CREATE TABLE IF NOT EXISTS attribution.style_attribution (
    style_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(50) NOT NULL,
    analysis_date DATE NOT NULL,
    style_factor VARCHAR(50) NOT NULL,
    portfolio_exposure DECIMAL(8,6) NOT NULL,
    benchmark_exposure DECIMAL(8,6) NOT NULL,
    factor_return DECIMAL(12,8) NOT NULL,
    attribution_value DECIMAL(12,8) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Transaction cost attribution
CREATE TABLE IF NOT EXISTS attribution.transaction_attribution (
    transaction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(50) NOT NULL,
    analysis_date DATE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    transaction_type VARCHAR(20) NOT NULL,
    shares_traded DECIMAL(20,8) NOT NULL,
    execution_price DECIMAL(20,8) NOT NULL,
    benchmark_price DECIMAL(20,8) NOT NULL,
    implementation_shortfall DECIMAL(12,8) NOT NULL,
    market_impact DECIMAL(12,8) NOT NULL,
    timing_cost DECIMAL(12,8) NOT NULL,
    total_transaction_cost DECIMAL(12,8) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE attribution.attribution_analysis IS 'Performance attribution analysis results';
COMMENT ON TABLE attribution.risk_attribution IS 'Risk factor attribution to portfolio returns';
COMMENT ON TABLE attribution.style_attribution IS 'Style factor attribution analysis';
COMMENT ON TABLE attribution.transaction_attribution IS 'Transaction cost attribution analysis';