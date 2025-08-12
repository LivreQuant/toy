-- global_static_data.sql
-- Global Static Data: metadata, universe_data, risk_factor_data
-- This data is shared across users and changes infrequently

-- =====================================================================================
-- INSERT UNIVERSE DATA
-- =====================================================================================
INSERT INTO exch_us_equity.universe_data (
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
    ('2025-08-12', 'AAPL', 'Technology', 'Consumer Electronics', 3000000000000, 'US', 'USD', 50000000, 1.2, 'NASDAQ', 15500000000),
    ('2025-08-12', 'MSFT', 'Technology', 'Software', 2800000000000, 'US', 'USD', 30000000, 0.9, 'NASDAQ', 7400000000),
    ('2025-08-12', 'GOOGL', 'Technology', 'Internet Services', 2000000000000, 'US', 'USD', 25000000, 1.1, 'NASDAQ', 12800000000),
    ('2025-08-12', 'AMZN', 'Consumer Discretionary', 'E-commerce', 1800000000000, 'US', 'USD', 35000000, 1.3, 'NASDAQ', 10700000000),
    ('2025-08-12', 'TSLA', 'Consumer Discretionary', 'Automotive', 800000000000, 'US', 'USD', 75000000, 2.0, 'NASDAQ', 3170000000);

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
    ('2025-08-12', 'AAPL', 'STYLE', 'GROWTH', 0.5),
    ('2025-08-12', 'AAPL', 'STYLE', 'MOMENTUM', 0.3),
    ('2025-08-12', 'AAPL', 'STYLE', 'QUALITY', 0.7),
    ('2025-08-12', 'AAPL', 'STYLE', 'VALUE', -0.2),
    ('2025-08-12', 'AAPL', 'STYLE', 'SIZE', -0.8),
    ('2025-08-12', 'AAPL', 'STYLE', 'VOLATILITY', 0.3),

    -- MSFT Risk Factors
    ('2025-08-12', 'MSFT', 'STYLE', 'GROWTH', 0.4),
    ('2025-08-12', 'MSFT', 'STYLE', 'MOMENTUM', 0.2),
    ('2025-08-12', 'MSFT', 'STYLE', 'QUALITY', 0.8),
    ('2025-08-12', 'MSFT', 'STYLE', 'VALUE', 0.1),
    ('2025-08-12', 'MSFT', 'STYLE', 'SIZE', -0.7),
    ('2025-08-12', 'MSFT', 'STYLE', 'VOLATILITY', 0.2),

    -- GOOGL Risk Factors
    ('2025-08-12', 'GOOGL', 'STYLE', 'GROWTH', 0.6),
    ('2025-08-12', 'GOOGL', 'STYLE', 'MOMENTUM', 0.1),
    ('2025-08-12', 'GOOGL', 'STYLE', 'QUALITY', 0.6),
    ('2025-08-12', 'GOOGL', 'STYLE', 'VALUE', -0.1),
    ('2025-08-12', 'GOOGL', 'STYLE', 'SIZE', -0.6),
    ('2025-08-12', 'GOOGL', 'STYLE', 'VOLATILITY', 0.4),

    -- AMZN Risk Factors
    ('2025-08-12', 'AMZN', 'STYLE', 'GROWTH', 0.8),
    ('2025-08-12', 'AMZN', 'STYLE', 'MOMENTUM', 0.4),
    ('2025-08-12', 'AMZN', 'STYLE', 'QUALITY', 0.5),
    ('2025-08-12', 'AMZN', 'STYLE', 'VALUE', -0.5),
    ('2025-08-12', 'AMZN', 'STYLE', 'SIZE', -0.5),
    ('2025-08-12', 'AMZN', 'STYLE', 'VOLATILITY', 0.6),

    -- TSLA Risk Factors
    ('2025-08-12', 'TSLA', 'STYLE', 'GROWTH', 0.9),
    ('2025-08-12', 'TSLA', 'STYLE', 'MOMENTUM', 0.7),
    ('2025-08-12', 'TSLA', 'STYLE', 'QUALITY', 0.3),
    ('2025-08-12', 'TSLA', 'STYLE', 'VALUE', -0.8),
    ('2025-08-12', 'TSLA', 'STYLE', 'SIZE', 0.2),
    ('2025-08-12', 'TSLA', 'STYLE', 'VOLATILITY', 1.2);

-- =====================================================================================
-- VERIFY GLOBAL STATIC DATA INSERTION
-- =====================================================================================
SELECT 'Global static data inserted successfully!' as status;

-- Show record counts
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