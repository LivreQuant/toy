-- db/schemas/views/portfolio_views.sql
-- Portfolio summary and analysis views

-- Portfolio summary view
CREATE OR REPLACE VIEW views.portfolio_summary AS
SELECT 
    p.account_id,
    p.position_date,
    COUNT(*) as total_positions,
    COUNT(CASE WHEN p.quantity > 0 THEN 1 END) as long_positions,
    COUNT(CASE WHEN p.quantity < 0 THEN 1 END) as short_positions,
    SUM(p.market_value) as total_market_value,
    SUM(p.unrealized_pnl) as total_unrealized_pnl,
    SUM(ABS(p.market_value)) as gross_market_value,
    AVG(p.market_value) as avg_position_size,
    STDDEV(p.market_value) as position_size_stddev,
    SUM(p.market_value) FILTER (WHERE p.quantity > 0) as long_market_value,
    SUM(p.market_value) FILTER (WHERE p.quantity < 0) as short_market_value
FROM positions.current_positions p
WHERE p.quantity != 0
GROUP BY p.account_id, p.position_date;

-- Position performance view
CREATE OR REPLACE VIEW views.position_performance AS
SELECT 
    p.account_id,
    p.symbol,
    p.position_date,
    p.quantity,
    p.market_value,
    p.unrealized_pnl,
    CASE 
        WHEN p.quantity * p.avg_cost != 0 
        THEN p.unrealized_pnl / (p.quantity * p.avg_cost) * 100 
        ELSE 0 
    END as unrealized_pnl_pct,
    s.company_name,
    s.sector,
    s.industry,
    ep.price as current_price,
    ep.price_change,
    ep.price_change_pct
FROM positions.current_positions p
LEFT JOIN reference_data.securities s ON p.symbol = s.symbol
LEFT JOIN positions.eod_prices ep ON p.symbol = ep.symbol AND p.position_date = ep.price_date
WHERE p.quantity != 0;

-- Sector allocation view
CREATE OR REPLACE VIEW views.sector_allocation AS
SELECT 
    p.account_id,
    p.position_date,
    COALESCE(s.sector, 'UNKNOWN') as sector,
    COUNT(*) as position_count,
    SUM(p.market_value) as sector_value,
    SUM(p.unrealized_pnl) as sector_pnl,
    AVG(p.market_value) as avg_position_value,
    SUM(p.market_value) / SUM(SUM(p.market_value)) OVER (PARTITION BY p.account_id, p.position_date) * 100 as allocation_pct
FROM positions.current_positions p
LEFT JOIN reference_data.securities s ON p.symbol = s.symbol
WHERE p.quantity != 0
GROUP BY p.account_id, p.position_date, s.sector;

-- Daily P&L summary view
CREATE OR REPLACE VIEW views.daily_pnl_summary AS
SELECT 
    pnl.account_id,
    pnl.pnl_date,
    SUM(pnl.realized_pnl) as total_realized_pnl,
    SUM(pnl.unrealized_pnl) as total_unrealized_pnl,
    SUM(pnl.total_pnl) as total_pnl,
    SUM(pnl.trading_pnl) as total_trading_pnl,
    SUM(pnl.dividends) as total_dividends,
    SUM(pnl.fees) as total_fees,
    COUNT(CASE WHEN pnl.total_pnl > 0 THEN 1 END) as winning_positions,
    COUNT(CASE WHEN pnl.total_pnl < 0 THEN 1 END) as losing_positions,
    COUNT(CASE WHEN pnl.symbol IS NOT NULL THEN 1 END) as total_positions_with_pnl
FROM pnl.daily_pnl pnl
WHERE pnl.symbol IS NOT NULL  -- Exclude portfolio-level records
GROUP BY pnl.account_id, pnl.pnl_date;

COMMENT ON VIEW views.portfolio_summary IS 'High-level portfolio statistics by account and date';
COMMENT ON VIEW views.position_performance IS 'Individual position performance with security details';
COMMENT ON VIEW views.sector_allocation IS 'Portfolio allocation breakdown by sector';
COMMENT ON VIEW views.daily_pnl_summary IS 'Daily P&L summary statistics by account';