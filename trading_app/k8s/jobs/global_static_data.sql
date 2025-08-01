-- global_static_data.sql
-- Global Static Data: metadata, universe_data, risk_factor_data
-- This data is shared across users and changes infrequently

-- =====================================================================================
-- INSERT UNIVERSE DATA
-- =====================================================================================
INSERT INTO exch_us_equity.universe_data (
    exchange_id,
    date,
    symbol,
    sector,
    industry,
    market_cap,
    country,
    currency,
    avg_daily_volume,
    beta,
    primary_exchange,
    shares_outstanding
) VALUES
    ('ABC', '2024-01-09', 'AAPL', 'Technology', 'Consumer Electronics', 3000000000000, 'US', 'USD', 50000000, 1.2, 'NASDAQ', 15500000000),
    ('ABC', '2024-01-09', 'MSFT', 'Technology', 'Software', 2800000000000, 'US', 'USD', 30000000, 0.9, 'NASDAQ', 7400000000),
    ('ABC', '2024-01-09', 'GOOGL', 'Technology', 'Internet Services', 2000000000000, 'US', 'USD', 25000000, 1.1, 'NASDAQ', 12800000000),
    ('ABC', '2024-01-09', 'AMZN', 'Consumer Discretionary', 'E-commerce', 1800000000000, 'US', 'USD', 35000000, 1.3, 'NASDAQ', 10700000000),
    ('ABC', '2024-01-09', 'TSLA', 'Consumer Discretionary', 'Automotive', 800000000000, 'US', 'USD', 75000000, 2.0, 'NASDAQ', 3170000000)
ON CONFLICT (date, symbol) DO UPDATE SET
    sector = EXCLUDED.sector,
    industry = EXCLUDED.industry,
    market_cap = EXCLUDED.market_cap,
    avg_daily_volume = EXCLUDED.avg_daily_volume,
    beta = EXCLUDED.beta,
    shares_outstanding = EXCLUDED.shares_outstanding;

-- =====================================================================================
-- INSERT RISK FACTOR DATA
-- =====================================================================================
INSERT INTO exch_us_equity.risk_factor_data (
    date,
    symbol,
    type,
    name,
    value
) VALUES
    -- AAPL Risk Factors
    ('2024-01-09', 'AAPL', 'STYLE', 'GROWTH', 0.5),
    ('2024-01-09', 'AAPL', 'STYLE', 'MOMENTUM', 0.3),
    ('2024-01-09', 'AAPL', 'STYLE', 'QUALITY', 0.7),
    ('2024-01-09', 'AAPL', 'STYLE', 'VALUE', -0.2),
    ('2024-01-09', 'AAPL', 'STYLE', 'SIZE', -0.8),
    ('2024-01-09', 'AAPL', 'STYLE', 'VOLATILITY', 0.3),

    -- MSFT Risk Factors
    ('2024-01-09', 'MSFT', 'STYLE', 'GROWTH', 0.4),
    ('2024-01-09', 'MSFT', 'STYLE', 'MOMENTUM', 0.2),
    ('2024-01-09', 'MSFT', 'STYLE', 'QUALITY', 0.8),
    ('2024-01-09', 'MSFT', 'STYLE', 'VALUE', 0.1),
    ('2024-01-09', 'MSFT', 'STYLE', 'SIZE', -0.7),
    ('2024-01-09', 'MSFT', 'STYLE', 'VOLATILITY', 0.2),

    -- GOOGL Risk Factors
    ('2024-01-09', 'GOOGL', 'STYLE', 'GROWTH', 0.6),
    ('2024-01-09', 'GOOGL', 'STYLE', 'MOMENTUM', 0.1),
    ('2024-01-09', 'GOOGL', 'STYLE', 'QUALITY', 0.6),
    ('2024-01-09', 'GOOGL', 'STYLE', 'VALUE', -0.1),
    ('2024-01-09', 'GOOGL', 'STYLE', 'SIZE', -0.6),
    ('2024-01-09', 'GOOGL', 'STYLE', 'VOLATILITY', 0.4),

    -- AMZN Risk Factors
    ('2024-01-09', 'AMZN', 'STYLE', 'GROWTH', 0.8),
    ('2024-01-09', 'AMZN', 'STYLE', 'MOMENTUM', 0.4),
    ('2024-01-09', 'AMZN', 'STYLE', 'QUALITY', 0.5),
    ('2024-01-09', 'AMZN', 'STYLE', 'VALUE', -0.5),
    ('2024-01-09', 'AMZN', 'STYLE', 'SIZE', -0.5),
    ('2024-01-09', 'AMZN', 'STYLE', 'VOLATILITY', 0.6),

    -- TSLA Risk Factors
    ('2024-01-09', 'TSLA', 'STYLE', 'GROWTH', 0.9),
    ('2024-01-09', 'TSLA', 'STYLE', 'MOMENTUM', 0.7),
    ('2024-01-09', 'TSLA', 'STYLE', 'QUALITY', 0.3),
    ('2024-01-09', 'TSLA', 'STYLE', 'VALUE', -0.8),
    ('2024-01-09', 'TSLA', 'STYLE', 'SIZE', 0.2),
    ('2024-01-09', 'TSLA', 'STYLE', 'VOLATILITY', 1.2)
ON CONFLICT (date, symbol, type, name) DO UPDATE SET
    value = EXCLUDED.value;

-- =====================================================================================
-- VERIFY GLOBAL STATIC DATA INSERTION
-- =====================================================================================
SELECT 'Global static data inserted successfully!' as status;

-- Show record counts
SELECT
    'metadata' as table_name,
    count(*) as records
FROM exch_us_equity.metadata
UNION ALL
SELECT
    'universe_data' as table_name,
    count(*) as records
FROM exch_us_equity.universe_data
UNION ALL
SELECT
    'risk_factor_data' as table_name,
    count(*) as records
FROM exch_us_equity.risk_factor_data
ORDER BY table_name;