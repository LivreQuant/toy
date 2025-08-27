-- db/schemas/views/risk_views.sql
-- Risk analysis and reporting views

-- Portfolio risk summary view
CREATE OR REPLACE VIEW views.portfolio_risk_summary AS
SELECT 
    pv.account_id,
    pv.calculation_date,
    pv.portfolio_value,
    pv.var_amount,
    pv.var_percentage,
    pv.expected_shortfall,
    pc.beta,
    pc.correlation,
    pc.tracking_error,
    pc.alpha_annual,
    CASE 
        WHEN pv.var_percentage <= 2.0 THEN 'LOW'
        WHEN pv.var_percentage <= 5.0 THEN 'MEDIUM'
        WHEN pv.var_percentage <= 10.0 THEN 'HIGH'
        ELSE 'VERY_HIGH'
    END as risk_category
FROM risk_metrics.portfolio_var pv
LEFT JOIN risk_metrics.portfolio_correlations pc 
    ON pv.account_id = pc.account_id 
    AND pv.calculation_date = pc.calculation_date
WHERE pv.confidence_level = 0.95 
    AND pv.holding_period = 1 
    AND pv.method = 'PARAMETRIC';

-- Risk limit utilization view
CREATE OR REPLACE VIEW views.risk_limit_utilization AS
SELECT 
    rl.account_id,
    rl.limit_type,
    rl.limit_name,
    rl.limit_value,
    rl.warning_threshold,
    re.exposure_value,
    re.exposure_percentage,
    re.limit_utilization_pct,
    re.breach_status,
    re.calculation_date,
    CASE 
        WHEN re.limit_utilization_pct >= 1.0 THEN 'BREACH'
        WHEN re.limit_utilization_pct >= rl.warning_threshold THEN 'WARNING'
        ELSE 'OK'
    END as alert_level,
    (re.exposure_value - rl.limit_value) as excess_amount
FROM risk_metrics.risk_limits rl
LEFT JOIN risk_metrics.risk_exposures re 
    ON rl.account_id = re.account_id 
    AND rl.limit_type = re.exposure_type 
    AND rl.limit_name = re.exposure_name
WHERE rl.is_active = TRUE;

-- Factor exposure analysis view
CREATE OR REPLACE VIEW views.factor_exposure_analysis AS
SELECT 
    fe.account_id,
    fe.calculation_date,
    fe.factor_name,
    rf.factor_type,
    fe.exposure_value,
    fe.exposure_percentage,
    rf.factor_volatility,
    (fe.exposure_value * rf.factor_volatility) as risk_contribution,
    RANK() OVER (
        PARTITION BY fe.account_id, fe.calculation_date 
        ORDER BY ABS(fe.exposure_value) DESC
    ) as exposure_rank
FROM risk_metrics.risk_exposures fe
JOIN risk_model.risk_factors rf 
    ON fe.exposure_name = rf.factor_name 
    AND fe.calculation_date = rf.factor_date
WHERE fe.exposure_type = 'FACTOR';

-- Sector risk concentration view
CREATE OR REPLACE VIEW views.sector_risk_concentration AS
SELECT 
    p.account_id,
    p.position_date,
    COALESCE(s.sector, 'UNKNOWN') as sector,
    COUNT(*) as position_count,
    SUM(p.market_value) as sector_exposure,
    SUM(p.market_value) / SUM(SUM(p.market_value)) OVER (
        PARTITION BY p.account_id, p.position_date
    ) * 100 as sector_weight_pct,
    STDDEV(p.unrealized_pnl / NULLIF(p.market_value, 0)) as sector_volatility,
    SUM(p.unrealized_pnl) as sector_pnl,
    AVG(lm.liquidity_score) as avg_liquidity_score
FROM positions.current_positions p
LEFT JOIN reference_data.securities s ON p.symbol = s.symbol
LEFT JOIN risk_metrics.liquidity_metrics lm 
    ON p.account_id = lm.account_id 
    AND p.symbol = lm.symbol 
    AND p.position_date = lm.calculation_date
WHERE p.quantity != 0
GROUP BY p.account_id, p.position_date, s.sector;

-- Stress test results summary view
CREATE OR REPLACE VIEW views.stress_test_summary AS
SELECT 
    st.account_id,
    st.test_date,
    sts.scenario_name,
    sts.scenario_type,
    st.portfolio_value,
    st.stress_pnl,
    st.stress_return_pct,
    st.worst_position,
    st.worst_position_pnl,
    RANK() OVER (
        PARTITION BY st.account_id, st.test_date 
        ORDER BY st.stress_pnl
    ) as stress_rank,
    CASE 
        WHEN st.stress_return_pct <= -0.20 THEN 'SEVERE'
        WHEN st.stress_return_pct <= -0.10 THEN 'HIGH'
        WHEN st.stress_return_pct <= -0.05 THEN 'MODERATE'
        ELSE 'LOW'
    END as stress_severity
FROM risk_metrics.stress_tests st
JOIN risk_metrics.stress_test_scenarios sts ON st.scenario_id = sts.scenario_id;

-- Liquidity risk analysis view
CREATE OR REPLACE VIEW views.liquidity_risk_analysis AS
SELECT 
    lm.account_id,
    lm.calculation_date,
    lm.liquidity_bucket,
    COUNT(*) as position_count,
    SUM(p.market_value) as total_exposure,
    SUM(p.market_value) / SUM(SUM(p.market_value)) OVER (
        PARTITION BY lm.account_id, lm.calculation_date
    ) * 100 as liquidity_weight_pct,
    AVG(lm.days_to_liquidate) as avg_days_to_liquidate,
    MAX(lm.days_to_liquidate) as max_days_to_liquidate,
    AVG(lm.bid_ask_spread_pct) as avg_spread_pct,
    AVG(lm.liquidity_score) as avg_liquidity_score
FROM risk_metrics.liquidity_metrics lm
JOIN positions.current_positions p 
    ON lm.account_id = p.account_id 
    AND lm.symbol = p.symbol 
    AND lm.calculation_date = p.position_date
WHERE p.quantity != 0
GROUP BY lm.account_id, lm.calculation_date, lm.liquidity_bucket;

-- Risk alert dashboard view
CREATE OR REPLACE VIEW views.risk_alert_dashboard AS
SELECT 
    ra.account_id,
    ra.alert_type,
    ra.alert_level,
    COUNT(*) as alert_count,
    COUNT(CASE WHEN ra.is_acknowledged = FALSE THEN 1 END) as unacknowledged_count,
    MIN(ra.created_at) as oldest_alert,
    MAX(ra.created_at) as newest_alert,
    COUNT(CASE WHEN ra.created_at >= CURRENT_DATE THEN 1 END) as today_alerts
FROM risk_metrics.risk_alerts ra
WHERE ra.created_at >= CURRENT_DATE - INTERVAL '7 days'
-- Continuing db/schemas/views/risk_views.sql

GROUP BY ra.account_id, ra.alert_type, ra.alert_level
ORDER BY 
   CASE ra.alert_level
       WHEN 'CRITICAL' THEN 1
       WHEN 'WARNING' THEN 2
       WHEN 'INFO' THEN 3
   END,
   unacknowledged_count DESC;

-- Factor model performance view
CREATE OR REPLACE VIEW views.factor_model_performance AS
SELECT 
   mv.model_name,
   mv.version_number,
   mv.effective_date,
   mv.factor_count,
   mv.universe_size,
   mv.average_r_squared,
   mp.evaluation_date,
   mp.bias_statistic,
   mp.volatility_forecast_error,
   mp.overall_model_score,
   RANK() OVER (
       PARTITION BY mv.model_name 
       ORDER BY mp.evaluation_date DESC, mp.overall_model_score DESC
   ) as model_rank
FROM risk_model.model_versions mv
LEFT JOIN risk_model.model_performance mp ON mv.version_id = mp.model_version_id
WHERE mv.is_active = TRUE;

-- Portfolio risk decomposition view
CREATE OR REPLACE VIEW views.portfolio_risk_decomposition AS
SELECT 
   rd.account_id,
   rd.calculation_date,
   rd.risk_type,
   rd.risk_category,
   rd.contribution_to_var,
   rd.marginal_var,
   rd.component_var,
   rd.diversification_ratio,
   SUM(rd.contribution_to_var) OVER (
       PARTITION BY rd.account_id, rd.calculation_date
   ) as total_var_contribution,
   rd.contribution_to_var / SUM(rd.contribution_to_var) OVER (
       PARTITION BY rd.account_id, rd.calculation_date
   ) * 100 as var_contribution_pct
FROM risk_metrics.risk_decomposition rd;

COMMENT ON VIEW views.portfolio_risk_summary IS 'High-level portfolio risk metrics summary';
COMMENT ON VIEW views.risk_limit_utilization IS 'Risk limit utilization and breach status';
COMMENT ON VIEW views.factor_exposure_analysis IS 'Factor exposure analysis with risk contribution';
COMMENT ON VIEW views.sector_risk_concentration IS 'Sector concentration and risk analysis';
COMMENT ON VIEW views.stress_test_summary IS 'Stress test results with severity ranking';
COMMENT ON VIEW views.liquidity_risk_analysis IS 'Portfolio liquidity risk breakdown';
COMMENT ON VIEW views.risk_alert_dashboard IS 'Risk alerts dashboard summary';
COMMENT ON VIEW views.factor_model_performance IS 'Risk model performance tracking';
COMMENT ON VIEW views.portfolio_risk_decomposition IS 'Risk decomposition by factor type';