-- =====================================================
-- State Management Schema
-- =====================================================
-- Purpose: System state persistence, operation logging, and recovery management
-- Version: 1.0
-- Created: 2025-08-26

-- Create schema
CREATE SCHEMA IF NOT EXISTS orchestrator;

-- =====================================================
-- SYSTEM STATE TABLE
-- =====================================================
-- Stores key-value pairs of system state information
CREATE TABLE IF NOT EXISTS orchestrator.system_state (
    id SERIAL PRIMARY KEY,
    state_key VARCHAR(50) NOT NULL UNIQUE,
    state_value JSONB,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_state_key_format CHECK (state_key ~ '^[a-z_]+$')
);

-- =====================================================
-- OPERATIONS LOG TABLE
-- =====================================================
-- Comprehensive log of all system operations
CREATE TABLE IF NOT EXISTS orchestrator.operations_log (
    id SERIAL PRIMARY KEY,
    operation_type VARCHAR(50) NOT NULL,
    operation_date DATE NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) NOT NULL,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_operation_type CHECK (operation_type IN (
        'SOD', 'EOD', 'EXCHANGE_START', 'EXCHANGE_STOP', 
        'SYSTEM_START', 'SYSTEM_STOP', 'HEALTH_CHECK',
        'DATA_SYNC', 'BACKUP', 'MAINTENANCE', 'ERROR_RECOVERY'
    )),
    CONSTRAINT chk_status CHECK (status IN (
        'STARTED', 'RUNNING', 'SUCCESS', 'FAILED', 
        'CANCELLED', 'TIMEOUT', 'PARTIAL_SUCCESS'
    )),
    CONSTRAINT chk_end_time_after_start CHECK (
        end_time IS NULL OR end_time >= start_time
    )
);

-- =====================================================
-- SYSTEM METRICS TABLE
-- =====================================================
-- Store system performance and health metrics over time
CREATE TABLE IF NOT EXISTS orchestrator.system_metrics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15,6) NOT NULL,
    metric_unit VARCHAR(20),
    metric_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metric_date DATE GENERATED ALWAYS AS (DATE(metric_timestamp AT TIME ZONE 'America/New_York')) STORED,
    tags JSONB DEFAULT '{}',
    
    CONSTRAINT chk_metric_name CHECK (metric_name ~ '^[a-z_]+$')
);

-- =====================================================
-- RECOVERY CHECKPOINTS TABLE
-- =====================================================
-- Store system recovery checkpoints for disaster recovery
CREATE TABLE IF NOT EXISTS orchestrator.recovery_checkpoints (
    id SERIAL PRIMARY KEY,
    checkpoint_name VARCHAR(100) NOT NULL,
    checkpoint_type VARCHAR(50) NOT NULL,
    checkpoint_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    
    CONSTRAINT chk_checkpoint_type CHECK (checkpoint_type IN (
        'SOD_COMPLETE', 'EOD_COMPLETE', 'TRADING_SESSION', 
        'DATA_SNAPSHOT', 'SYSTEM_BACKUP', 'ERROR_STATE'
    )),
    CONSTRAINT uk_checkpoint_name_type UNIQUE(checkpoint_name, checkpoint_type)
);

-- =====================================================
-- SYSTEM ALERTS TABLE
-- =====================================================
-- Store system alerts and notifications
CREATE TABLE IF NOT EXISTS orchestrator.system_alerts (
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    alert_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    acknowledged_by VARCHAR(100),
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolved_by VARCHAR(100),
    
    CONSTRAINT chk_alert_type CHECK (alert_type IN (
        'SYSTEM_ERROR', 'DATABASE_ERROR', 'EXCHANGE_ERROR',
        'SOD_FAILURE', 'EOD_FAILURE', 'HEALTH_CHECK_FAIL',
        'PERFORMANCE_DEGRADATION', 'RESOURCE_EXHAUSTION',
        'SECURITY_INCIDENT', 'DATA_QUALITY_ISSUE'
    )),
    CONSTRAINT chk_severity CHECK (severity IN (
        'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'
    ))
);

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================

-- System state indexes
CREATE INDEX IF NOT EXISTS idx_system_state_key 
ON orchestrator.system_state(state_key);

CREATE INDEX IF NOT EXISTS idx_system_state_updated_at 
ON orchestrator.system_state(updated_at DESC);

-- Operations log indexes
CREATE INDEX IF NOT EXISTS idx_operations_log_type_date 
ON orchestrator.operations_log(operation_type, operation_date DESC);

CREATE INDEX IF NOT EXISTS idx_operations_log_status 
ON orchestrator.operations_log(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_operations_log_created_at 
ON orchestrator.operations_log(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_operations_log_operation_date 
ON orchestrator.operations_log(operation_date DESC);

-- System metrics indexes
CREATE INDEX IF NOT EXISTS idx_system_metrics_name_timestamp 
ON orchestrator.system_metrics(metric_name, metric_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_system_metrics_date 
ON orchestrator.system_metrics(metric_date DESC);

CREATE INDEX IF NOT EXISTS idx_system_metrics_tags 
ON orchestrator.system_metrics USING GIN(tags);

-- Recovery checkpoints indexes
CREATE INDEX IF NOT EXISTS idx_recovery_checkpoints_type 
ON orchestrator.recovery_checkpoints(checkpoint_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_recovery_checkpoints_active 
ON orchestrator.recovery_checkpoints(is_active, created_at DESC)
WHERE is_active = TRUE;

-- System alerts indexes
CREATE INDEX IF NOT EXISTS idx_system_alerts_type_severity 
ON orchestrator.system_alerts(alert_type, severity, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_system_alerts_unresolved 
ON orchestrator.system_alerts(created_at DESC)
WHERE resolved_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_system_alerts_created_at 
ON orchestrator.system_alerts(created_at DESC);

-- =====================================================
-- PARTITIONING (Optional - for high-volume environments)
-- =====================================================

-- Partition operations_log by month for better performance
-- Uncomment if you expect high volume of operations
/*
ALTER TABLE orchestrator.operations_log 
PARTITION BY RANGE (operation_date);

-- Create partitions for current and next few months
-- This would need to be managed by a maintenance job
CREATE TABLE orchestrator.operations_log_y2025m08 
PARTITION OF orchestrator.operations_log
FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');

CREATE TABLE orchestrator.operations_log_y2025m09 
PARTITION OF orchestrator.operations_log
FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');
*/

-- =====================================================
-- FUNCTIONS AND TRIGGERS
-- =====================================================

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION orchestrator.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for system_state table
DROP TRIGGER IF EXISTS trigger_system_state_updated_at ON orchestrator.system_state;
CREATE TRIGGER trigger_system_state_updated_at
    BEFORE UPDATE ON orchestrator.system_state
    FOR EACH ROW
    EXECUTE FUNCTION orchestrator.update_updated_at_column();

-- Function to clean up old operations logs
CREATE OR REPLACE FUNCTION orchestrator.cleanup_old_operations(days_to_keep INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
    cutoff_date DATE;
BEGIN
    cutoff_date := CURRENT_DATE - INTERVAL '1 day' * days_to_keep;
    
    DELETE FROM orchestrator.operations_log 
    WHERE operation_date < cutoff_date;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    -- Log the cleanup operation
    INSERT INTO orchestrator.operations_log 
    (operation_type, operation_date, start_time, end_time, status, details)
    VALUES (
        'MAINTENANCE',
        CURRENT_DATE,
        NOW(),
        NOW(),
        'SUCCESS',
        jsonb_build_object(
            'action', 'cleanup_old_operations',
            'cutoff_date', cutoff_date,
            'deleted_count', deleted_count
        )
    );
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to get system health summary
CREATE OR REPLACE FUNCTION orchestrator.get_system_health_summary(lookback_hours INTEGER DEFAULT 24)
RETURNS JSONB AS $$
DECLARE
    result JSONB;
    cutoff_timestamp TIMESTAMP WITH TIME ZONE;
BEGIN
    cutoff_timestamp := NOW() - INTERVAL '1 hour' * lookback_hours;
    
    SELECT jsonb_build_object(
        'total_operations', COUNT(*),
        'successful_operations', COUNT(*) FILTER (WHERE status = 'SUCCESS'),
        'failed_operations', COUNT(*) FILTER (WHERE status = 'FAILED'),
        'running_operations', COUNT(*) FILTER (WHERE status = 'RUNNING'),
        'last_sod_status', (
            SELECT jsonb_build_object('status', status, 'timestamp', start_time)
            FROM orchestrator.operations_log 
            WHERE operation_type = 'SOD' 
            ORDER BY start_time DESC 
            LIMIT 1
        ),
        'last_eod_status', (
            SELECT jsonb_build_object('status', status, 'timestamp', start_time)
            FROM orchestrator.operations_log 
            WHERE operation_type = 'EOD' 
            ORDER BY start_time DESC 
            LIMIT 1
        ),
        'unresolved_alerts', (
            SELECT COUNT(*) 
            FROM orchestrator.system_alerts 
            WHERE resolved_at IS NULL AND severity IN ('CRITICAL', 'HIGH')
        )
    ) INTO result
    FROM orchestrator.operations_log
    WHERE created_at >= cutoff_timestamp;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- VIEWS FOR COMMON QUERIES
-- =====================================================

-- View for recent operations with duration
CREATE OR REPLACE VIEW orchestrator.v_recent_operations AS
SELECT 
    id,
    operation_type,
    operation_date,
    start_time,
    end_time,
    EXTRACT(EPOCH FROM (COALESCE(end_time, NOW()) - start_time)) AS duration_seconds,
    status,
    details,
    created_at
FROM orchestrator.operations_log
ORDER BY created_at DESC;

-- View for current system state summary
CREATE OR REPLACE VIEW orchestrator.v_system_state_summary AS
SELECT 
    jsonb_object_agg(state_key, state_value) AS current_state,
    MAX(updated_at) AS last_updated
FROM orchestrator.system_state;

-- View for daily operation summary
CREATE OR REPLACE VIEW orchestrator.v_daily_operations AS
SELECT 
    operation_date,
    operation_type,
    COUNT(*) as operation_count,
    COUNT(*) FILTER (WHERE status = 'SUCCESS') as successful_count,
    COUNT(*) FILTER (WHERE status = 'FAILED') as failed_count,
    AVG(EXTRACT(EPOCH FROM (end_time - start_time))) as avg_duration_seconds,
    MIN(start_time) as first_operation,
    MAX(COALESCE(end_time, start_time)) as last_operation
FROM orchestrator.operations_log
WHERE end_time IS NOT NULL
GROUP BY operation_date, operation_type
ORDER BY operation_date DESC, operation_type;

-- =====================================================
-- COMMENTS AND DOCUMENTATION
-- =====================================================

COMMENT ON SCHEMA orchestrator IS 'System orchestration, state management, and operational logging';

COMMENT ON TABLE orchestrator.system_state IS 'Key-value store for system state persistence and recovery';
COMMENT ON COLUMN orchestrator.system_state.state_key IS 'Unique identifier for state value (e.g., last_sod, last_eod, current_state)';
COMMENT ON COLUMN orchestrator.system_state.state_value IS 'JSON object containing state data and metadata';

COMMENT ON TABLE orchestrator.operations_log IS 'Comprehensive audit log of all system operations';
COMMENT ON COLUMN orchestrator.operations_log.operation_date IS 'Business date in ET timezone for operation grouping';
COMMENT ON COLUMN orchestrator.operations_log.start_time IS 'UTC timestamp when operation started';
COMMENT ON COLUMN orchestrator.operations_log.end_time IS 'UTC timestamp when operation completed (null if still running)';

COMMENT ON TABLE orchestrator.system_metrics IS 'Time-series data for system performance monitoring';
COMMENT ON COLUMN orchestrator.system_metrics.metric_date IS 'Generated column: business date in ET timezone';
COMMENT ON COLUMN orchestrator.system_metrics.tags IS 'Additional metadata for metric filtering and grouping';

COMMENT ON TABLE orchestrator.recovery_checkpoints IS 'System recovery checkpoints for disaster recovery scenarios';
COMMENT ON COLUMN orchestrator.recovery_checkpoints.expires_at IS 'When this checkpoint expires and can be cleaned up';

COMMENT ON TABLE orchestrator.system_alerts IS 'System alerts and notifications requiring attention';
COMMENT ON COLUMN orchestrator.system_alerts.acknowledged_at IS 'When alert was acknowledged by operator';
COMMENT ON COLUMN orchestrator.system_alerts.resolved_at IS 'When underlying issue was resolved';

COMMENT ON FUNCTION orchestrator.cleanup_old_operations(INTEGER) IS 'Cleanup old operation log entries beyond retention period';
COMMENT ON FUNCTION orchestrator.get_system_health_summary(INTEGER) IS 'Get comprehensive system health summary for specified lookback period';

COMMENT ON VIEW orchestrator.v_recent_operations IS 'Recent operations with calculated duration';
COMMENT ON VIEW orchestrator.v_system_state_summary IS 'Current system state as aggregated JSON object';
COMMENT ON VIEW orchestrator.v_daily_operations IS 'Daily summary of operations by type with statistics';

-- =====================================================
-- SAMPLE DATA (for testing/development)
-- =====================================================

-- Insert initial state keys
INSERT INTO orchestrator.system_state (state_key, state_value) VALUES
('current_state', '{"state": "idle", "timestamp": "2025-08-26T10:00:00Z"}'),
('system_info', '{"version": "1.0.0", "environment": "production", "startup_time": "2025-08-26T09:00:00Z"}')
ON CONFLICT (state_key) DO NOTHING;

-- Grant permissions (adjust as needed for your environment)
-- GRANT USAGE ON SCHEMA orchestrator TO trading_app_role;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA orchestrator TO trading_app_role;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA orchestrator TO trading_app_role;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA orchestrator TO trading_app_role;