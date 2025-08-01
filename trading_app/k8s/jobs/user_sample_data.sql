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
    gen_random_uuid(),
    'US_EQUITIES',
    'America/New_York',
    ARRAY['NYSE', 'NASDAQ', 'ARCA'],
    '2024-01-09T00:00:00+00:00'::TIMESTAMP WITH TIME ZONE,
    '04:00:00'::TIME,
    '09:30:00'::TIME,
    '16:00:00'::TIME,
    '20:00:00'::TIME
) ON CONFLICT (group_id) DO UPDATE SET
    last_snap = EXCLUDED.last_snap,
    updated_time = CURRENT_TIMESTAMP;

-- =====================================================================================
-- INSERT USER
-- =====================================================================================
INSERT INTO exch_us_equity.users (
    user_id,
    exch_id,
    base_currency,
    timezone
) VALUES
    ('USER_000', (SELECT exch_id FROM exch_us_equity.metadata WHERE group_id = 'ABC'), 'USD', 'America/New_York')
ON CONFLICT (user_id) DO UPDATE SET
    base_currency = EXCLUDED.base_currency,
    timezone = EXCLUDED.timezone;

-- =====================================================================================
-- INSERT PORTFOLIO DATA
-- =====================================================================================
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
    -- TEMPLATE_USER portfolio
    ('USER_000', '2024-01-09T00:00:00+00:00'::TIMESTAMP WITH TIME ZONE, 'AAPL', 1000, 'USD', 180.50, 187450.00, 0.0, 6950.00, 0.0, 6950.00)
ON CONFLICT (user_id, timestamp, symbol) DO UPDATE SET
    quantity = EXCLUDED.quantity,
    avg_price = EXCLUDED.avg_price,
    mtm_value = EXCLUDED.mtm_value,
    sod_realized_pnl = EXCLUDED.sod_realized_pnl,
    itd_realized_pnl = EXCLUDED.itd_realized_pnl,
    realized_pnl = EXCLUDED.realized_pnl,
    unrealized_pnl = EXCLUDED.unrealized_pnl;

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
    ('USER_000', '2024-01-09T00:00:00+00:00'::TIMESTAMP WITH TIME ZONE, 'CREDIT', 'USD', 1000000.0, 1000000.0, 0.0),
    ('USER_000', '2024-01-09T00:00:00+00:00'::TIMESTAMP WITH TIME ZONE, 'SHORT_CREDIT', 'USD', 0.0, 0.0, 0.0),
    ('USER_000', '2024-01-09T00:00:00+00:00'::TIMESTAMP WITH TIME ZONE, 'DEBIT', 'USD', 575000.0, 575000.0, 0.0)
ON CONFLICT (user_id, timestamp, type, currency) DO UPDATE SET
    amount = EXCLUDED.amount,
    previous_amount = EXCLUDED.previous_amount,
    change = EXCLUDED.change;

-- =====================================================================================
-- INSERT RETURN DATA
-- =====================================================================================
INSERT INTO cccc.return_data (
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
    ('USER_000', '2024-01-09T00:00:00+00:00'::TIMESTAMP WITH TIME ZONE, 'WTD_BOOK_NAV', 'BOOK', 'NAV', 425450.0, 415000.0, 415000.0, 0.0, 0.0252, 0.0252, 100.0, 0.0252, 0.0252),
    ('USER_000', '2024-01-09T00:00:00+00:00'::TIMESTAMP WITH TIME ZONE, 'MTD_BOOK_NAV', 'BOOK', 'NAV', 425450.0, 415000.0, 415000.0, 0.0, 0.0252, 0.0252, 100.0, 0.0252, 0.0252),
    ('USER_000', '2024-01-09T00:00:00+00:00'::TIMESTAMP WITH TIME ZONE, 'YTD_BOOK_NAV', 'BOOK', 'NAV', 425450.0, 415000.0, 415000.0, 0.0, 0.0252, 0.0252, 100.0, 0.0252, 0.0252),
    ('USER_000', '2024-01-09T00:00:00+00:00'::TIMESTAMP WITH TIME ZONE, 'WTD_CASH_EQUITY_EQUITY', 'CASH_EQUITY', 'EQUITY', 425450.0, 415000.0, 415000.0, 0.0, 0.0252, 0.0252, 100.0, 0.0252, 0.0252),
    ('USER_000', '2024-01-09T00:00:00+00:00'::TIMESTAMP WITH TIME ZONE, 'WTD_CASH_EQUITY_CASH', 'CASH_EQUITY', 'CASH', 425000.0, 425000.0, 425000.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
ON CONFLICT (user_id, timestamp, return_id) DO UPDATE SET
   category = EXCLUDED.category,
   subcategory = EXCLUDED.subcategory,
   emv = EXCLUDED.emv,
   bmv = EXCLUDED.bmv,
   bmv_book = EXCLUDED.bmv_book,
   cf = EXCLUDED.cf,
   periodic_return_subcategory = EXCLUDED.periodic_return_subcategory,
   cumulative_return_subcategory = EXCLUDED.cumulative_return_subcategory,
   contribution_percentage = EXCLUDED.contribution_percentage,
   periodic_return_contribution = EXCLUDED.periodic_return_contribution,
   cumulative_return_contribution = EXCLUDED.cumulative_return_contribution;

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