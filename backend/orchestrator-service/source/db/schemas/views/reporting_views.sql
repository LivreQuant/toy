-- db/schemas/views/reporting_views.sql
-- Reporting and analytics views

-- Daily trading summary view
CREATE OR REPLACE VIEW views.daily_trading_summary AS
SELECT 
    t.account_id,
    t.trade_date,
    COUNT(*) as total_trades,
    COUNT(CASE WHEN t.side = 'BUY' THEN 1 END) as buy_trades,
    COUNT(CASE WHEN t.side = 'SELL' THEN 1 END) as sell_trades,
    SUM(ABS(t.trade_value)) as total_volume,
    SUM(t.commission + t.fees) as total_costs,
    AVG(ABS(t.trade_value)) as avg_trade_size,
    COUNT(DISTINCT t.symbol) as unique_symbols,
    SUM(CASE WHEN t.side = 'BUY' THEN t.trade_value ELSE 0 END) as buy_volume,
    SUM(CASE WHEN t.side = 'SELL' THEN t.trade_value ELSE 0 END) as sell_volume,
    (SUM(CASE WHEN t.side = 'BUY' THEN t.trade_value ELSE 0 END) - 
     SUM(CASE WHEN t.side = 'SELL' THEN t.trade_value ELSE 0 END)) as net_trading_flow
FROM settlement.trades t
GROUP BY t.account_id, t.trade_date;

-- Portfolio performance dashboard view
CREATE OR REPLACE VIEW views.portfolio_performance_dashboard AS
SELECT 
    pp.account_id,
    pp.performance_date,
    pp.portfolio_value,
    pp.total_return_pct,
    pp.benchmark_return_pct,
    pp.excess_return_pct,
    pp.volatility_pct,
    pp.sharpe_ratio,
    pp.max_drawdown_pct,
    pp.beta,
    pp.alpha_pct,
    pnl.total_realized_pnl,
    pnl.total_unrealized_pnl,
    pnl.total_pnl,
    pnl.winning_positions,
    pnl.losing_positions,
    CASE 
        WHEN pp.total_return_pct > pp.benchmark_return_pct THEN 'OUTPERFORMING'
        WHEN pp.total_return_pct < pp.benchmark_return_pct THEN 'UNDERPERFORMING'
        ELSE 'INLINE'
    END as performance_vs_benchmark
FROM pnl.portfolio_performance pp
LEFT JOIN views.daily_pnl_summary pnl 
    ON pp.account_id = pnl.account_id 
    AND pp.performance_date = pnl.pnl_date;

-- Settlement status dashboard view
CREATE OR REPLACE VIEW views.settlement_status_dashboard AS
SELECT 
    t.settlement_date,
    t.settlement_status,
    COUNT(*) as trade_count,
    SUM(ABS(t.trade_value)) as total_value,
    COUNT(DISTINCT t.account_id) as unique_accounts,
    COUNT(DISTINCT t.symbol) as unique_symbols,
    AVG(EXTRACT(EPOCH FROM (t.updated_at - t.created_at))/3600) as avg_processing_hours,
    SUM(t.commission + t.fees) as total_fees
FROM settlement.trades t
WHERE t.settlement_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY t.settlement_date, t.settlement_status
ORDER BY t.settlement_date DESC, 
    CASE t.settlement_status
        WHEN 'FAILED' THEN 1
        WHEN 'PENDING' THEN 2
        WHEN 'MATCHED' THEN 3
        WHEN 'SETTLED' THEN 4
    END;

-- Top performers view
CREATE OR REPLACE VIEW views.top_performers AS
SELECT 
    pnl.account_id,
    pnl.pnl_date,
    pnl.symbol,
    s.company_name,
    s.sector,
    pnl.total_pnl,
    pnl.unrealized_pnl,
    pnl.realized_pnl,
    pnl.market_value_end,
    CASE 
        WHEN pnl.market_value_start > 0 
        THEN pnl.total_pnl / pnl.market_value_start * 100 
        ELSE 0 
    END as return_pct,
    ROW_NUMBER() OVER (
        PARTITION BY pnl.account_id, pnl.pnl_date 
        ORDER BY pnl.total_pnl DESC
    ) as profit_rank,
    ROW_NUMBER() OVER (
        PARTITION BY pnl.account_id, pnl.pnl_date 
        ORDER BY pnl.total_pnl ASC
    ) as loss_rank
FROM pnl.daily_pnl pnl
LEFT JOIN reference_data.securities s ON pnl.symbol = s.symbol
WHERE pnl.symbol IS NOT NULL;

-- Corporate actions impact view
CREATE OR REPLACE VIEW views.corporate_actions_impact AS
SELECT 
    ca.symbol,
    ca.action_type,
    ca.ex_date,
    ca.amount,
    ca.ratio,
    ca.status,
    COUNT(p.account_id) as affected_accounts,
    SUM(p.quantity) as total_shares_affected,
    SUM(p.market_value) as total_value_affected,
    SUM(CASE 
        WHEN ca.action_type = 'DIVIDEND' AND ca.amount IS NOT NULL 
        THEN p.quantity * ca.amount 
        ELSE 0 
    END) as estimated_dividend_payment
FROM corporate_actions.actions ca
LEFT JOIN positions.current_positions p 
    ON ca.symbol = p.symbol 
    AND p.position_date = ca.ex_date 
    AND p.quantity > 0
GROUP BY ca.symbol, ca.action_type, ca.ex_date, ca.amount, ca.ratio, ca.status;

-- Reconciliation breaks summary view
CREATE OR REPLACE VIEW views.reconciliation_breaks_summary AS
SELECT 
    rb.recon_date,
    rb.break_type,
    rb.resolution_status,
    COUNT(*) as break_count,
    SUM(ABS(rb.impact_amount)) as total_impact,
    AVG(ABS(rb.impact_amount)) as avg_impact,
    COUNT(DISTINCT rb.account_id) as affected_accounts,
    MIN(rb.created_at) as oldest_break,
    COUNT(CASE WHEN rb.assigned_to IS NOT NULL THEN 1 END) as assigned_breaks,
    COUNT(CASE WHEN rb.resolved_at IS NOT NULL THEN 1 END) as resolved_breaks
FROM reconciliation.recon_breaks rb
WHERE rb.recon_date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY rb.recon_date, rb.break_type, rb.resolution_status;

-- Exchange performance summary view
CREATE OR REPLACE VIEW views.exchange_performance_summary AS
SELECT 
    em.exch_id,
    em.exchange_type,
    em.exchanges,
    pm.metric_date,
    SUM(pm.messages_received) as daily_messages_received,
    SUM(pm.messages_processed) as daily_messages_processed,
    SUM(pm.messages_rejected) as daily_messages_rejected,
    AVG(pm.avg_latency_ms) as avg_latency_ms,
    MAX(pm.max_latency_ms) as max_latency_ms,
    SUM(pm.error_count) as total_errors,
    AVG(pm.uptime_percentage) as avg_uptime_pct,
    CASE 
        WHEN AVG(pm.uptime_percentage) >= 99.5 THEN 'EXCELLENT'
        WHEN AVG(pm.uptime_percentage) >= 99.0 THEN 'GOOD'
        WHEN AVG(pm.uptime_percentage) >= 95.0 THEN 'ACCEPTABLE'
        ELSE 'POOR'
    END as performance_grade
FROM exch_us_equity.metadata em
LEFT JOIN exch_us_equity.performance_metrics pm ON em.exch_id = pm.exch_id
GROUP BY em.exch_id, em.exchange_type, em.exchanges, pm.metric_date;

-- Account summary view
CREATE OR REPLACE VIEW views.account_summary AS
SELECT 
    ps.account_id,
    ps.position_date,
    ps.total_market_value,
    ps.total_unrealized_pnl,
    ps.long_market_value,
    ps.short_market_value,
    ps.total_positions,
    sa.sector_count,
    pp.total_return_pct,
    pp.volatility_pct,
    pp.sharpe_ratio,
    pv.var_amount,
    pv.var_percentage,
    ts.total_trades,
    ts.total_volume,
    COALESCE(ps.long_market_value, 0) / NULLIF(ABS(COALESCE(ps.short_market_value, 0)), 0) as long_short_ratio
FROM views.portfolio_summary ps
LEFT JOIN (
    SELECT account_id, position_date, COUNT(DISTINCT sector) as sector_count
    FROM views.sector_allocation 
    GROUP BY account_id, position_date
) sa ON ps.account_id = sa.account_id AND ps.position_date = sa.position_date
LEFT JOIN pnl.portfolio_performance pp 
    ON ps.account_id = pp.account_id AND ps.position_date = pp.performance_date
LEFT JOIN risk_metrics.portfolio_var pv 
    ON ps.account_id = pv.account_id AND ps.position_date = pv.calculation_date 
    AND pv.confidence_level = 0.95 AND pv.holding_period = 1
LEFT JOIN views.daily_trading_summary ts 
    ON ps.account_id = ts.account_id AND ps.position_date = ts.trade_date;

-- Workflow execution summary view
CREATE OR REPLACE VIEW views.workflow_execution_summary AS
SELECT 
    we.workflow_name,
    we.workflow_type,
    we.execution_date,
    we.workflow_status,
    we.total_tasks,
    we.completed_tasks,
    we.failed_tasks,
    EXTRACT(EPOCH FROM (we.completed_at - we.started_at))/60 as duration_minutes,
    we.completed_tasks::FLOAT / NULLIF(we.total_tasks, 0) * 100 as completion_percentage,
    COUNT(wt.task_id) as task_count,
    AVG(wt.duration_seconds) as avg_task_duration_seconds,
    MAX(wt.duration_seconds) as max_task_duration_seconds
FROM workflows.workflow_executions we
LEFT JOIN workflows.workflow_tasks wt ON we.execution_id = wt.workflow_execution_id
WHERE we.execution_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY we.execution_id, we.workflow_name, we.workflow_type, we.execution_date, 
         we.workflow_status, we.total_tasks, we.completed_tasks, we.failed_tasks,
         we.started_at, we.completed_at;

-- Market data quality summary view
CREATE OR REPLACE VIEW views.market_data_quality_summary AS
SELECT 
    dqm.metric_date,
    em.exchange_type,
    COUNT(DISTINCT dqm.symbol) as symbols_monitored,
    AVG(dqm.quality_score) as avg_quality_score,
    COUNT(CASE WHEN dqm.quality_score >= 90 THEN 1 END) as high_quality_symbols,
    COUNT(CASE WHEN dqm.quality_score < 70 THEN 1 END) as poor_quality_symbols,
    SUM(dqm.stale_quotes) as total_stale_quotes,
    SUM(dqm.crossed_quotes) as total_crossed_quotes,
    SUM(dqm.wide_spreads) as total_wide_spreads,
    AVG(dqm.quality_score) as overall_quality_score
FROM exch_us_equity.data_quality_metrics dqm
LEFT JOIN exch_us_equity.metadata em ON dqm.exch_id = em.exch_id
WHERE dqm.metric_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY dqm.metric_date, em.exchange_type
ORDER BY dqm.metric_date DESC;

COMMENT ON VIEW views.daily_trading_summary IS 'Daily trading activity summary by account';
COMMENT ON VIEW views.portfolio_performance_dashboard IS 'Portfolio performance dashboard with key metrics';
COMMENT ON VIEW views.settlement_status_dashboard IS 'Trade settlement status monitoring dashboard';
COMMENT ON VIEW views.top_performers IS 'Top and bottom performing positions by P&L';
COMMENT ON VIEW views.corporate_actions_impact IS 'Corporate actions impact on portfolios';
COMMENT ON VIEW views.reconciliation_breaks_summary IS 'Reconciliation breaks status summary';
COMMENT ON VIEW views.exchange_performance_summary IS 'Exchange connectivity and performance summary';
COMMENT ON VIEW views.account_summary IS 'Comprehensive account summary with key metrics';
COMMENT ON VIEW views.workflow_execution_summary IS 'Workflow execution status and performance';
COMMENT ON VIEW views.market_data_quality_summary IS 'Market data quality monitoring summary';