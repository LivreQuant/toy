-- db/schemas/risk/risk_model.sql
-- Risk factor model tables

-- Risk factors (style, macro, industry)
CREATE TABLE IF NOT EXISTS risk_model.risk_factors (
    factor_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    factor_date DATE NOT NULL,
    factor_type VARCHAR(50) NOT NULL CHECK (factor_type IN ('STYLE', 'MACRO', 'INDUSTRY', 'COUNTRY', 'CURRENCY', 'SECTOR')),
    factor_name VARCHAR(100) NOT NULL,
    factor_value DECIMAL(12,8) NOT NULL,
    factor_volatility DECIMAL(12,8),
    factor_description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
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
    confidence_interval_lower DECIMAL(12,8),
    confidence_interval_upper DECIMAL(12,8),
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
    p_value DECIMAL(8,6),
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
    eigenvalue DECIMAL(12,8),
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
    var_95 DECIMAL(12,8),
    var_99 DECIMAL(12,8),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_factor_statistics UNIQUE(factor_date, factor_name)
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
    specific_return DECIMAL(12,8),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_specific_risk UNIQUE(factor_date, symbol),
    CONSTRAINT chk_specific_risk_positive CHECK (specific_risk >= 0),
    CONSTRAINT chk_total_risk_composition CHECK (ABS(total_risk - (systematic_risk + specific_risk)) < 0.0001)
);

-- Factor model versions and metadata
CREATE TABLE IF NOT EXISTS risk_model.model_versions (
    version_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_name VARCHAR(100) NOT NULL,
    version_number VARCHAR(20) NOT NULL,
    effective_date DATE NOT NULL,
    model_type VARCHAR(50) NOT NULL CHECK (model_type IN ('FUNDAMENTAL', 'STATISTICAL', 'MIXED')),
    factor_count INTEGER NOT NULL,
    universe_size INTEGER NOT NULL,
    average_r_squared DECIMAL(8,6),
    model_description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_model_versions UNIQUE(model_name, version_number)
);

-- Factor model performance tracking
CREATE TABLE IF NOT EXISTS risk_model.model_performance (
    performance_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_version_id UUID REFERENCES risk_model.model_versions(version_id),
    evaluation_date DATE NOT NULL,
    forecast_horizon INTEGER NOT NULL,
    bias_statistic DECIMAL(12,8),
    volatility_forecast_error DECIMAL(12,8),
    correlation_forecast_error DECIMAL(12,8),
    factor_mimicking_r_squared DECIMAL(8,6),
    specific_risk_forecast_accuracy DECIMAL(8,6),
    overall_model_score DECIMAL(8,4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Factor hierarchies and groupings
CREATE TABLE IF NOT EXISTS risk_model.factor_hierarchies (
    hierarchy_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parent_factor VARCHAR(100),
    child_factor VARCHAR(100) NOT NULL,
    hierarchy_level INTEGER NOT NULL,
    weight DECIMAL(8,6) DEFAULT 1.0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_hierarchy_level CHECK (hierarchy_level > 0),
    CONSTRAINT chk_weight_valid CHECK (weight BETWEEN 0 AND 1)
);

-- Regional and sector mappings
CREATE TABLE IF NOT EXISTS risk_model.factor_mappings (
    mapping_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    effective_date DATE NOT NULL,
    region VARCHAR(50),
    country VARCHAR(3),
    sector VARCHAR(100),
    industry VARCHAR(100),
    sub_industry VARCHAR(100),
    market_cap_bucket VARCHAR(20),
    style_classification VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_factor_mappings UNIQUE(symbol, effective_date)
);

-- Factor return calculations
CREATE TABLE IF NOT EXISTS risk_model.factor_returns (
    return_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    factor_name VARCHAR(100) NOT NULL,
    return_date DATE NOT NULL,
    return_value DECIMAL(12,8) NOT NULL,
    return_source VARCHAR(50) NOT NULL,
    calculation_method VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_factor_returns UNIQUE(factor_name, return_date, return_source)
);

-- Comments
COMMENT ON TABLE risk_model.risk_factors IS 'Master table of risk factors with daily values';
COMMENT ON TABLE risk_model.factor_exposures IS 'Security exposures to risk factors';
COMMENT ON TABLE risk_model.factor_loadings IS 'Regression-based factor loadings';
COMMENT ON TABLE risk_model.factor_covariance IS 'Factor covariance and correlation matrix';
COMMENT ON TABLE risk_model.factor_statistics IS 'Statistical properties of factors';
COMMENT ON TABLE risk_model.specific_risk IS 'Idiosyncratic risk not explained by factors';
COMMENT ON TABLE risk_model.model_versions IS 'Risk model versions and metadata';
COMMENT ON TABLE risk_model.model_performance IS 'Risk model backtesting and performance';
COMMENT ON TABLE risk_model.factor_hierarchies IS 'Factor groupings and hierarchical structure';
COMMENT ON TABLE risk_model.factor_mappings IS 'Security classifications for factor assignment';
COMMENT ON TABLE risk_model.factor_returns IS 'Historical factor returns from various sources';