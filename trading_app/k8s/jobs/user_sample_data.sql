-- user_sample_data.sql
-- User-Specific Sample Data: users, portfolio_data, account_data, etc.
-- This data is specific to individual users

-- =====================================================================================
-- INSERT EXCHANGE METADATA
-- =====================================================================================
INSERT INTO exch_us_equity.metadata (
    exch_id,
    exchange_type,

    timezone,
    exchanges,
    last_snap,
    pre_market_open,
    market_open,
    market_close,
    post_market_close
) VALUES (
    '00000000-0000-0000-0000-000000000002'::UUID,
    'US_EQUITIES',
    'America/New_York',
    ARRAY['NYSE', 'NASDAQ', 'ARCA'],
    '2025-08-01T20:45:00+00:00'::TIMESTAMP WITH TIME ZONE,
    '04:00:00'::TIME,
    '09:30:00'::TIME,
    '16:00:00'::TIME,
    '20:00:00'::TIME
);

-- =====================================================================================
-- INSERT USER
-- =====================================================================================
INSERT INTO exch_us_equity.users (
    user_id,
    exch_id,
    base_currency,
    timezone
) VALUES (
    '00000000-0000-0000-0000-000000000001', 
    '00000000-0000-0000-0000-000000000002', 
    'USD', 
    'America/New_York'
);

-- =====================================================================================
-- INSERT PORTFOLIO DATA
-- =====================================================================================
/*
INSERT INTO exch_us_equity.portfolio_data (
    user_id,
    timestamp,
    symbol,
    quantity,
    currency,
    avg_price,
    mtm_value,
    sod_realized_pnl,
    itd_realized_pnl,
    realized_pnl,
    unrealized_pnl
) VALUES 
    ('00000000-0000-0000-0000-000000000001', '2024-01-09T00:00:00+00:00'::TIMESTAMP WITH TIME ZONE, 'AAPL', 1000, 'USD', 180.50, 187450.00, 0.0, 6950.00, 0.0, 6950.00);
*/

-- =====================================================================================
-- INSERT ACCOUNT DATA
-- =====================================================================================
INSERT INTO exch_us_equity.account_data (
    user_id,
    timestamp,
    type,
    currency,
    amount,
    previous_amount,
    change
) VALUES
    -- TEMPLATE_USER accounts
    ('00000000-0000-0000-0000-000000000001', '2025-08-01T20:45:00+00:00'::TIMESTAMP WITH TIME ZONE, 'CREDIT', 'USD', 1000000.0, 1000000.0, 0.0),
    ('00000000-0000-0000-0000-000000000001', '2025-08-01T20:45:00+00:00'::TIMESTAMP WITH TIME ZONE, 'SHORT_CREDIT', 'USD', 0.0, 0.0, 0.0),
    ('00000000-0000-0000-0000-000000000001', '2025-08-01T20:45:00+00:00'::TIMESTAMP WITH TIME ZONE, 'DEBIT', 'USD', 0.0, 0.0, 0.0);

-- =====================================================================================
-- INSERT RETURN DATA
-- =====================================================================================
/*
INSERT INTO exch_us_equity.return_data (
    user_id,
    timestamp,
    return_id,
    category,
    subcategory,
    emv,
    bmv,
    bmv_book,
    cf,
    periodic_return_subcategory,
    cumulative_return_subcategory,
    contribution_percentage,
    periodic_return_contribution,
    cumulative_return_contribution
) VALUES
    -- TEMPLATE_USER returns
    ('00000000-0000-0000-0000-000000000001', '2024-01-09T00:00:00+00:00'::TIMESTAMP WITH TIME ZONE, 'WTD_BOOK_NAV', 'BOOK', 'NAV', 425450.0, 415000.0, 415000.0, 0.0, 0.0252, 0.0252, 100.0, 0.0252, 0.0252),
    ('00000000-0000-0000-0000-000000000001', '2024-01-09T00:00:00+00:00'::TIMESTAMP WITH TIME ZONE, 'MTD_BOOK_NAV', 'BOOK', 'NAV', 425450.0, 415000.0, 415000.0, 0.0, 0.0252, 0.0252, 100.0, 0.0252, 0.0252),
    ('00000000-0000-0000-0000-000000000001', '2024-01-09T00:00:00+00:00'::TIMESTAMP WITH TIME ZONE, 'YTD_BOOK_NAV', 'BOOK', 'NAV', 425450.0, 415000.0, 415000.0, 0.0, 0.0252, 0.0252, 100.0, 0.0252, 0.0252),
    ('00000000-0000-0000-0000-000000000001', '2024-01-09T00:00:00+00:00'::TIMESTAMP WITH TIME ZONE, 'WTD_CASH_EQUITY_EQUITY', 'CASH_EQUITY', 'EQUITY', 425450.0, 415000.0, 415000.0, 0.0, 0.0252, 0.0252, 100.0, 0.0252, 0.0252),
    ('00000000-0000-0000-0000-000000000001', '2024-01-09T00:00:00+00:00'::TIMESTAMP WITH TIME ZONE, 'WTD_CASH_EQUITY_CASH', 'CASH_EQUITY', 'CASH', 425000.0, 425000.0, 425000.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0);
*/

-- =====================================================================================
-- VERIFY USER DATA INSERTION
-- =====================================================================================
SELECT 'User sample data inserted successfully!' as status;

-- Show record counts
SELECT
   'users' as table_name,
   count(*) as records
FROM exch_us_equity.users
UNION ALL
SELECT
   'portfolio_data' as table_name,
   count(*) as records
FROM exch_us_equity.portfolio_data
UNION ALL
SELECT
   'account_data' as table_name,
   count(*) as records
FROM exch_us_equity.account_data
UNION ALL
SELECT
   'cash_flow_data' as table_name,
   count(*) as records
FROM exch_us_equity.cash_flow_data
UNION ALL
SELECT
   'return_data' as table_name,
   count(*) as records
FROM exch_us_equity.return_data
UNION ALL
SELECT
   'portfolio_risk_data' as table_name,
   count(*) as records
FROM exch_us_equity.portfolio_risk_data
ORDER BY table_name;