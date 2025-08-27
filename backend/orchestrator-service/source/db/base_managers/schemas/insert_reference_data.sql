-- db/schemas/insert_reference_data.sql
-- Insert essential reference data

-- Insert default exchanges
INSERT INTO reference_data.exchanges (exchange_id, exchange_name, country, timezone, currency, market_open, market_close) VALUES
('NYSE', 'New York Stock Exchange', 'USA', 'America/New_York', 'USD', '09:30:00', '16:00:00'),
('NASDAQ', 'NASDAQ Stock Market', 'USA', 'America/New_York', 'USD', '09:30:00', '16:00:00'),
('LSE', 'London Stock Exchange', 'GBR', 'Europe/London', 'GBP', '08:00:00', '16:30:00'),
('TSE', 'Tokyo Stock Exchange', 'JPN', 'Asia/Tokyo', 'JPY', '09:00:00', '15:00:00')
ON CONFLICT (exchange_id) DO NOTHING;

-- Insert default benchmarks
INSERT INTO pnl.performance_benchmarks (benchmark_code, benchmark_name, benchmark_type, currency, provider) VALUES
('SPX', 'S&P 500 Index', 'INDEX', 'USD', 'S&P Dow Jones Indices'),
('NDX', 'NASDAQ 100 Index', 'INDEX', 'USD', 'NASDAQ'),
('RUT', 'Russell 2000 Index', 'INDEX', 'USD', 'Russell Investments'),
('CUSTOM_BALANCED', 'Custom Balanced Portfolio', 'CUSTOM', 'USD', 'Internal')
ON CONFLICT (benchmark_code) DO NOTHING;

-- Insert exchange metadata for orchestrator
INSERT INTO exch_us_equity.metadata (
    exch_id, 
    exchange_type, 
    exchanges, 
    timezone,
    pre_market_open,
    market_open,
    market_close, 
    post_market_close,
    endpoint,
    pod_name,
    namespace
) VALUES 
(
    uuid_generate_v4(),
    'US_EQUITIES',
    ARRAY['NYSE', 'NASDAQ'],
    'America/New_York',
    '04:00:00'::TIME,
    '09:30:00'::TIME,
    '16:00:00'::TIME,
    '20:00:00'::TIME,
    'exchange-service-us-equities-001:50055',
    'exchange-service-us-equities-001',
    'default'
) ON CONFLICT (exch_id) DO NOTHING;

-- Insert sample securities
INSERT INTO reference_data.securities (symbol, company_name, sector, industry, exchange, market_cap, currency, country) VALUES
('AAPL', 'Apple Inc.', 'TECHNOLOGY', 'Consumer Electronics', 'NASDAQ', 3000000000000, 'USD', 'USA'),
('MSFT', 'Microsoft Corporation', 'TECHNOLOGY', 'Software', 'NASDAQ', 2800000000000, 'USD', 'USA'),
('GOOGL', 'Alphabet Inc. Class A', 'COMMUNICATION_SERVICES', 'Internet Services', 'NASDAQ', 1700000000000, 'USD', 'USA'),
('AMZN', 'Amazon.com Inc.', 'CONSUMER_DISCRETIONARY', 'E-commerce', 'NASDAQ', 1500000000000, 'USD', 'USA'),
('TSLA', 'Tesla Inc.', 'CONSUMER_DISCRETIONARY', 'Electric Vehicles', 'NASDAQ', 800000000000, 'USD', 'USA'),
('META', 'Meta Platforms Inc.', 'COMMUNICATION_SERVICES', 'Social Media', 'NASDAQ', 750000000000, 'USD', 'USA'),
('NVDA', 'NVIDIA Corporation', 'TECHNOLOGY', 'Semiconductors', 'NASDAQ', 1800000000000, 'USD', 'USA'),
('NFLX', 'Netflix Inc.', 'COMMUNICATION_SERVICES', 'Streaming', 'NASDAQ', 200000000000, 'USD', 'USA'),
('JPM', 'JPMorgan Chase & Co.', 'FINANCIALS', 'Banking', 'NYSE', 450000000000, 'USD', 'USA'),
('JNJ', 'Johnson & Johnson', 'HEALTHCARE', 'Pharmaceuticals', 'NYSE', 400000000000, 'USD', 'USA')
ON CONFLICT (symbol) DO UPDATE SET
    company_name = EXCLUDED.company_name,
    sector = EXCLUDED.sector,
    industry = EXCLUDED.industry,
    market_cap = EXCLUDED.market_cap,
    updated_at = NOW();

-- Insert system configuration
INSERT INTO system_config.configuration (config_key, config_value, config_type, description) VALUES
('DEFAULT_COMMISSION', '5.00', 'DECIMAL', 'Default commission per trade'),
('DEFAULT_CURRENCY', 'USD', 'STRING', 'Default currency for calculations'),
('RISK_FREE_RATE', '0.05', 'DECIMAL', 'Annual risk-free rate for calculations'),
('VAR_CONFIDENCE_LEVEL', '0.95', 'DECIMAL', 'Default VaR confidence level'),
('MAX_POSITION_SIZE_PCT', '5.0', 'DECIMAL', 'Maximum position size as % of portfolio'),
('SETTLEMENT_DAYS_T_PLUS', '2', 'INTEGER', 'Standard settlement period in days')
ON CONFLICT (config_key) DO UPDATE SET 
    config_value = EXCLUDED.config_value,
    updated_at = NOW();

-- Insert retention policies
INSERT INTO archival.retention_policies (data_type, retention_days, storage_tier, compression_type, archival_frequency) VALUES
('daily_pnl', 2555, 'STANDARD', 'gzip', 'DAILY'),
('positions', 2555, 'STANDARD', 'gzip', 'DAILY'),
('trades', 2555, 'STANDARD', 'gzip', 'DAILY'),
('risk_metrics', 1095, 'STANDARD', 'gzip', 'DAILY'),
('market_data', 365, 'COLD', 'bzip2', 'DAILY'),
('reports', 730, 'STANDARD', 'gzip', 'WEEKLY')
ON CONFLICT (data_type) DO UPDATE SET
    retention_days = EXCLUDED.retention_days,
    updated_at = NOW();