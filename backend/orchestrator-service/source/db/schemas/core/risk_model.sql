-- db/schemas/core/risk_model.sql
-- Risk model tables for factor analysis

-- Risk factors (style, macro, industry)
CREATE TABLE IF NOT EXISTS risk_model.risk_factors (
    factor_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    factor_date DATE NOT NULL,
    factor_type VARCHAR(50) NOT NULL CHECK (factor_type IN ('STYLE', 'MACRO', 'INDUSTRY', 'COUNTRY', 'CURRENCY')),
    factor_name VARCHAR(100) NOT NULL,
    factor_value DECIMAL(12,8) NOT NULL,
    factor_volatility DECIMAL(12,8),
    factor_description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_risk_factors_date_type_name UNIQUE(factor_date, factor_type, factor_name)
);

-- Security factor exposures
CREATE TABLE IF NOT EXISTS risk_model.factor_exposures (
    exposure_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    factor_date DATE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    factor_name VARCHAR(100) NOT NULL,
    exposure DECIMAL(12,8) NOT NULL,
    t_statistic DECIMAL(8,4),
    r_squared DECIMAL(8,6),
    standard_error DECIMAL(12,8),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_factor_exposures UNIQUE(factor_date, symbol, factor_name)
);

-- Factor loadings from regression analysis
CREATE TABLE IF NOT EXISTS risk_model.factor_loadings (
    loading_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    factor_date DATE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    factor_name VARCHAR(100) NOT NULL,
    loading DECIMAL(12,6) NOT NULL,
    t_statistic DECIMAL(8,4),
    r_squared DECIMAL(8,6),
    standard_error DECIMAL(12,6),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_factor_loadings UNIQUE(factor_date, symbol, factor_name)
);

-- Factor covariance matrix
CREATE TABLE IF NOT EXISTS risk_model.factor_covariance (
    covariance_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    factor_date DATE NOT NULL,
    factor1 VARCHAR(100) NOT NULL,
    factor2 VARCHAR(100) NOT NULL,
    covariance DECIMAL(12,8) NOT NULL,
    correlation DECIMAL(8,6),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_factor_covariance UNIQUE(factor_date, factor1, factor2)
);

-- Factor statistics and performance
CREATE TABLE IF NOT EXISTS risk_model.factor_statistics (
    stat_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    factor_date DATE NOT NULL,
    factor_name VARCHAR(100) NOT NULL,
    mean_return DECIMAL(12,6) NOT NULL,
    volatility DECIMAL(12,6) NOT NULL,
    skewness DECIMAL(8,4),
    kurtosis DECIMAL(8,4),
    max_drawdown DECIMAL(8,4),
    sharpe_ratio DECIMAL(8,4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_factor_statistics UNIQUE(factor_date, factor_name)
);

-- Portfolio VaR table
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
    method VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(account_id, calculation_date, confidence_level, holding_period, method)
);

-- Stress test results
CREATE TABLE IF NOT EXISTS risk_metrics.stress_tests (
    stress_test_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(50) NOT NULL,
    test_date DATE NOT NULL,
    scenario_name VARCHAR(100) NOT NULL,
    scenario_type VARCHAR(50) NOT NULL,
    stress_pnl DECIMAL(20,2) NOT NULL,
    stress_return_pct DECIMAL(8,4) NOT NULL,
    portfolio_value DECIMAL(20,2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Risk exposures
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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Specific risk (idiosyncratic risk)
CREATE TABLE IF NOT EXISTS risk_model.specific_risk (
    risk_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    factor_date DATE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    specific_risk DECIMAL(12,8) NOT NULL,
    total_risk DECIMAL(12,8) NOT NULL,
    systematic_risk DECIMAL(12,8) NOT NULL,
    r_squared DECIMAL(8,6),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_specific_risk UNIQUE(factor_date, symbol),
    CONSTRAINT chk_specific_risk_positive CHECK (specific_risk >= 0)
);

-- Comments
COMMENT ON TABLE risk_model.risk_factors IS 'Factor returns and characteristics by date';
COMMENT ON TABLE risk_model.factor_exposures IS 'Security exposures to risk factors';
COMMENT ON TABLE risk_model.factor_loadings IS 'Regression loadings from factor model';
COMMENT ON TABLE risk_model.factor_covariance IS 'Factor covariance and correlation matrix';
COMMENT ON TABLE risk_model.factor_statistics IS 'Statistical properties of risk factors';
COMMENT ON TABLE risk_model.specific_risk IS 'Idiosyncratic risk not explained by factors';
COMMENT ON TABLE risk_metrics.portfolio_var IS 'Portfolio Value at Risk calculations';
COMMENT ON TABLE risk_metrics.stress_tests IS 'Stress test scenario results';
COMMENT ON TABLE risk_metrics.risk_exposures IS 'Portfolio risk exposures and limits';