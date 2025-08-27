-- db/schemas/reference/securities.sql
-- Security master and reference data

CREATE TABLE IF NOT EXISTS reference_data.securities (
    security_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL UNIQUE,
    company_name VARCHAR(200),
    sector VARCHAR(100),
    industry VARCHAR(100),
    country VARCHAR(3) DEFAULT 'USA',
    currency VARCHAR(3) DEFAULT 'USD',
    exchange VARCHAR(50),
    market_cap DECIMAL(20,2),
    shares_outstanding DECIMAL(20,0),
    is_active BOOLEAN DEFAULT TRUE,
    listing_date DATE,
    delisting_date DATE,
    security_type VARCHAR(50) DEFAULT 'EQUITY',
    isin VARCHAR(12),
    cusip VARCHAR(9),
    sedol VARCHAR(7),
    bloomberg_id VARCHAR(50),
    reuters_id VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Corporate actions
CREATE TABLE IF NOT EXISTS reference_data.corporate_actions (
    action_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    ex_date DATE NOT NULL,
    record_date DATE,
    pay_date DATE,
    amount DECIMAL(20,8),
    ratio DECIMAL(20,8),
    description TEXT,
    status VARCHAR(20) DEFAULT 'PENDING',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE reference_data.securities IS 'Master security reference data';
COMMENT ON TABLE reference_data.corporate_actions IS 'Corporate action events affecting securities';