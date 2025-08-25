-- db/schemas/risk/risk_metrics.sql
-- Risk metrics and measurement tables

-- Portfolio VaR calculations
CREATE TABLE IF NOT EXISTS risk_metrics.portfolio_var (
    var_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(50) NOT NULL,
    calculation_date DATE NOT NULL,
    confidence_level DECIMAL(5,3) NOT NULL,
    holding_period INTEGER NOT NULL,
    var_amount DECIMAL(20,2) NOT NULL,
    expected_shortfall DECIMAL(20,2),
    portfolio_value DECIMAL(20,2) NOT NULL,
    var_percentage DECIMAL(8,4) NOT NULL,
    method VARCHAR(50) NOT NULL CHECK (method IN ('PARAMETRIC', 'HISTORICAL', 'MONTE_CARLO')),
    model_parameters JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_portfolio_var UNIQUE(account_id, calculation_date, confidence_level, holding_period, method)
);

-- Stress test scenarios and results
CREATE TABLE IF NOT EXISTS risk_metrics.stress_test_scenarios (
    scenario_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scenario_name VARCHAR(100) NOT NULL UNIQUE,
    scenario_type VARCHAR(50) NOT NULL CHECK (scenario_type IN ('HISTORICAL', 'HYPOTHETICAL', 'REGULATORY')),
    scenario_description TEXT,
    shock_parameters JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS risk_metrics.stress_tests (
    stress_test_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(50) NOT NULL,
    scenario_id UUID REFERENCES risk_metrics.stress_test_scenarios(scenario_id),
    test_date DATE NOT NULL,
    stress_pnl DECIMAL(20,2) NOT NULL,
    stress_return_pct DECIMAL(8,4) NOT NULL,
    portfolio_value DECIMAL(20,2) NOT NULL,
    worst_position VARCHAR(20),
    worst_position_pnl DECIMAL(20,2),
    calculation_details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Risk exposures and limits
CREATE TABLE IF NOT EXISTS risk_metrics.risk_limits (
    limit_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(50) NOT NULL,
    limit_type VARCHAR(50) NOT NULL,
    limit_name VARCHAR(100) NOT NULL,
    limit_value DECIMAL(20,2) NOT NULL,
    warning_threshold DECIMAL(8,4) DEFAULT 0.8,
    currency VARCHAR(3) DEFAULT 'USD',
    is_active BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_risk_limits UNIQUE(account_id, limit_type, limit_name)
);

CREATE TABLE IF NOT EXISTS risk_metrics.risk_exposures (
    exposure_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(50) NOT NULL,
    calculation_date DATE NOT NULL,
    exposure_type VARCHAR(50) NOT NULL,
    exposure_name VARCHAR(100) NOT NULL,
    exposure_value DECIMAL(20,2) NOT NULL,
    exposure_percentage DECIMAL(8,4) NOT NULL,
    limit_value DECIMAL(20,2),
    limit_utilization_pct DECIMAL(8,4),
    breach_status VARCHAR(20) DEFAULT 'OK' CHECK (breach_status IN ('OK', 'WARNING', 'BREACH')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Risk limit breaches
CREATE TABLE IF NOT EXISTS risk_metrics.limit_breaches (
    breach_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(50) NOT NULL,
    limit_id UUID REFERENCES risk_metrics.risk_limits(limit_id),
    breach_date DATE NOT NULL,
    breach_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    exposure_value DECIMAL(20,2) NOT NULL,
    limit_value DECIMAL(20,2) NOT NULL,
    breach_amount DECIMAL(20,2) NOT NULL,
    breach_percentage DECIMAL(8,4) NOT NULL,
    breach_severity VARCHAR(20) NOT NULL CHECK (breach_severity IN ('WARNING', 'MINOR', 'MAJOR', 'CRITICAL')),
    status VARCHAR(20) DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')),
    acknowledged_by VARCHAR(100),
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Portfolio beta and correlation metrics
CREATE TABLE IF NOT EXISTS risk_metrics.portfolio_correlations (
    correlation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(50) NOT NULL,
    calculation_date DATE NOT NULL,
    benchmark_id UUID REFERENCES pnl.performance_benchmarks(benchmark_id),
    correlation DECIMAL(8,6) NOT NULL,
    beta DECIMAL(8,4) NOT NULL,
    alpha_annual DECIMAL(8,4),
    r_squared DECIMAL(8,6),
    tracking_error DECIMAL(8,4),
    information_ratio DECIMAL(8,4),
    lookback_days INTEGER DEFAULT 252,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_portfolio_correlations UNIQUE(account_id, calculation_date, benchmark_id)
);

-- Sector and factor risk decomposition
CREATE TABLE IF NOT EXISTS risk_metrics.risk_decomposition (
    decomposition_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(50) NOT NULL,
    calculation_date DATE NOT NULL,
    risk_type VARCHAR(50) NOT NULL CHECK (risk_type IN ('SECTOR', 'FACTOR', 'CURRENCY', 'COUNTRY')),
    risk_category VARCHAR(100) NOT NULL,
    contribution_to_var DECIMAL(12,8) NOT NULL,
    marginal_var DECIMAL(12,8) NOT NULL,
    component_var DECIMAL(12,8) NOT NULL,
    diversification_ratio DECIMAL(8,6),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Liquidity risk metrics
CREATE TABLE IF NOT EXISTS risk_metrics.liquidity_metrics (
    liquidity_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(50) NOT NULL,
    calculation_date DATE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    position_size DECIMAL(20,8) NOT NULL,
    avg_daily_volume BIGINT,
    days_to_liquidate DECIMAL(8,2),
    bid_ask_spread_pct DECIMAL(8,4),
    liquidity_score DECIMAL(5,2),
    liquidity_bucket VARCHAR(20) CHECK (liquidity_bucket IN ('HIGH', 'MEDIUM', 'LOW', 'ILLIQUID')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_liquidity_metrics UNIQUE(account_id, calculation_date, symbol)
);

-- Risk alerts and notifications
CREATE TABLE IF NOT EXISTS risk_metrics.risk_alerts (
    alert_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(50) NOT NULL,
    alert_type VARCHAR(50) NOT NULL,
    alert_level VARCHAR(20) NOT NULL CHECK (alert_level IN ('INFO', 'WARNING', 'CRITICAL')),
    alert_message TEXT NOT NULL,
    alert_data JSONB,
    is_acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(100),
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Comments
COMMENT ON TABLE risk_metrics.portfolio_var IS 'Portfolio Value at Risk calculations by method and confidence level';
COMMENT ON TABLE risk_metrics.stress_test_scenarios IS 'Predefined stress test scenarios';
COMMENT ON TABLE risk_metrics.stress_tests IS 'Stress test results for portfolios';
COMMENT ON TABLE risk_metrics.risk_limits IS 'Risk limits and thresholds by account';
COMMENT ON TABLE risk_metrics.risk_exposures IS 'Current risk exposures vs limits';
COMMENT ON TABLE risk_metrics.limit_breaches IS 'Risk limit breaches requiring attention';
COMMENT ON TABLE risk_metrics.portfolio_correlations IS 'Portfolio correlation and beta metrics';
COMMENT ON TABLE risk_metrics.risk_decomposition IS 'Risk contribution decomposition by factor';
COMMENT ON TABLE risk_metrics.liquidity_metrics IS 'Position liquidity risk assessment';
COMMENT ON TABLE risk_metrics.risk_alerts IS 'Risk monitoring alerts and notifications';