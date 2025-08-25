-- db/schemas/create_indexes.sql
-- Comprehensive index creation for performance optimization

-- Position table indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_positions_account_date 
    ON positions.current_positions(account_id, position_date);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_positions_symbol_date 
    ON positions.current_positions(symbol, position_date);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_positions_date_nonzero 
    ON positions.current_positions(position_date) WHERE quantity != 0;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_position_history_date 
    ON positions.position_history(position_date);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_position_history_account_symbol 
    ON positions.position_history(account_id, symbol, position_date);

-- Price table indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_eod_prices_symbol_date 
    ON positions.eod_prices(symbol, price_date);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_eod_prices_date_source 
    ON positions.eod_prices(price_date, pricing_source);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_intraday_prices_symbol_time 
    ON positions.intraday_prices(symbol, price_timestamp);

-- Trade table indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_account_date 
    ON settlement.trades(account_id, trade_date);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_settlement_status 
    ON settlement.trades(settlement_date, settlement_status);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_symbol_date 
    ON settlement.trades(symbol, trade_date);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_execution_time 
    ON settlement.trades(execution_time);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_venue 
    ON settlement.trades(venue, trade_date);

-- P&L table indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_daily_pnl_account_date 
    ON pnl.daily_pnl(account_id, pnl_date);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_daily_pnl_date 
    ON pnl.daily_pnl(pnl_date);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_daily_pnl_symbol_date 
    ON pnl.daily_pnl(symbol, pnl_date) WHERE symbol IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_portfolio_performance_account 
    ON pnl.portfolio_performance(account_id, performance_date);

-- Risk model indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_risk_factors_date_type 
    ON risk_model.risk_factors(factor_date, factor_type);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_factor_exposures_symbol_date 
    ON risk_model.factor_exposures(symbol, factor_date);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_factor_exposures_factor 
    ON risk_model.factor_exposures(factor_name, factor_date);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_portfolio_var_account_date 
    ON risk_metrics.portfolio_var(account_id, calculation_date);

-- Reference data indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_securities_sector 
    ON reference_data.securities(sector) WHERE is_active = TRUE;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_securities_exchange 
    ON reference_data.securities(exchange) WHERE is_active = TRUE;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_securities_market_cap 
    ON reference_data.securities(market_cap DESC NULLS LAST) WHERE is_active = TRUE;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_corporate_actions_symbol_date 
    ON reference_data.corporate_actions(symbol, ex_date);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_corporate_actions_date_status 
    ON reference_data.corporate_actions(ex_date, status);

-- Universe indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_universe_date_tradeable 
    ON universe.trading_universe(universe_date, is_tradeable);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_universe_symbol 
    ON universe.trading_universe(symbol, universe_date);

-- Reconciliation indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_position_recon_date 
    ON reconciliation.position_recon(recon_date);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_position_recon_breaks 
    ON reconciliation.position_recon(recon_date, tolerance_breached) WHERE tolerance_breached = TRUE;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cash_recon_date 
    ON reconciliation.cash_recon(recon_date);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_recon_breaks_status 
    ON reconciliation.recon_breaks(resolution_status, recon_date) WHERE resolution_status = 'OPEN';

-- Workflow indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workflows_status_date 
    ON workflows.workflow_executions(workflow_status, execution_date);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workflow_tasks_status 
    ON workflows.workflow_tasks(task_status, workflow_execution_id);

-- Partial indexes for better performance on common queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_positions_current_nonzero 
    ON positions.current_positions(account_id, symbol) WHERE quantity != 0;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_pending_settlement 
    ON settlement.trades(settlement_date) WHERE settlement_status = 'PENDING';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_prices_latest_by_symbol 
    ON positions.eod_prices(symbol, price_date DESC, pricing_source) WHERE pricing_source = 'MARKET';

-- Function-based indexes for common calculations
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_positions_abs_market_value 
    ON positions.current_positions(account_id, ABS(market_value)) WHERE quantity != 0;

-- Composite indexes for complex queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_account_symbol_date 
    ON settlement.trades(account_id, symbol, trade_date);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pnl_account_symbol_date 
    ON pnl.daily_pnl(account_id, COALESCE(symbol, ''), pnl_date);