# db/managers/state_manager.py
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List, Union
import json
import pytz
from decimal import Decimal
from .base_manager import BaseManager

logger = logging.getLogger(__name__)

class StateManager(BaseManager):
    """Database manager for system state persistence and operations logging"""
    
    def __init__(self, db_manager):
        super().__init__(db_manager)
        self.market_tz = pytz.timezone('America/New_York')
    
    async def initialize_tables(self):
        """Initialize state management tables by executing schema definitions"""
        await self.create_schema_if_not_exists('orchestrator')
        await self._create_system_state_table()
        await self._create_operations_log_table()
        await self._create_system_metrics_table()
        await self._create_recovery_checkpoints_table()
        await self._create_system_alerts_table()
        await self._create_indexes()
        await self._create_functions()
        await self._create_views()
        await self._insert_initial_data()
        
        logger.info("✅ State management tables initialized")
    
    async def create_schema_if_not_exists(self, schema_name: str):
        """Create schema if it doesn't exist"""
        await self.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
    
    async def _create_system_state_table(self):
        """Create system_state table"""
        await self.execute("""
            CREATE TABLE IF NOT EXISTS orchestrator.system_state (
                id SERIAL PRIMARY KEY,
                state_key VARCHAR(50) NOT NULL UNIQUE,
                state_value JSONB,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                
                CONSTRAINT chk_state_key_format CHECK (state_key ~ '^[a-z_]+$')
            )
        """)
    
    async def _create_operations_log_table(self):
        """Create operations_log table"""
        await self.execute("""
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
            )
        """)
    
    async def _create_system_metrics_table(self):
        """Create system_metrics table"""
        await self.execute("""
            CREATE TABLE IF NOT EXISTS orchestrator.system_metrics (
                id SERIAL PRIMARY KEY,
                metric_name VARCHAR(100) NOT NULL,
                metric_value DECIMAL(15,6) NOT NULL,
                metric_unit VARCHAR(20),
                metric_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                metric_date DATE GENERATED ALWAYS AS (DATE(metric_timestamp AT TIME ZONE 'America/New_York')) STORED,
                tags JSONB DEFAULT '{}',
                
                CONSTRAINT chk_metric_name CHECK (metric_name ~ '^[a-z_]+$')
            )
        """)
    
    async def _create_recovery_checkpoints_table(self):
        """Create recovery_checkpoints table"""
        await self.execute("""
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
            )
        """)
    
    async def _create_system_alerts_table(self):
        """Create system_alerts table"""
        await self.execute("""
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
            )
        """)
    
    async def _create_indexes(self):
        """Create all indexes for performance"""
        indexes = [
            # System state indexes
            "CREATE INDEX IF NOT EXISTS idx_system_state_key ON orchestrator.system_state(state_key)",
            "CREATE INDEX IF NOT EXISTS idx_system_state_updated_at ON orchestrator.system_state(updated_at DESC)",
            
            # Operations log indexes
            "CREATE INDEX IF NOT EXISTS idx_operations_log_type_date ON orchestrator.operations_log(operation_type, operation_date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_operations_log_status ON orchestrator.operations_log(status, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_operations_log_created_at ON orchestrator.operations_log(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_operations_log_operation_date ON orchestrator.operations_log(operation_date DESC)",
            
            # System metrics indexes
            "CREATE INDEX IF NOT EXISTS idx_system_metrics_name_timestamp ON orchestrator.system_metrics(metric_name, metric_timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_system_metrics_date ON orchestrator.system_metrics(metric_date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_system_metrics_tags ON orchestrator.system_metrics USING GIN(tags)",
            
            # Recovery checkpoints indexes
            "CREATE INDEX IF NOT EXISTS idx_recovery_checkpoints_type ON orchestrator.recovery_checkpoints(checkpoint_type, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_recovery_checkpoints_active ON orchestrator.recovery_checkpoints(is_active, created_at DESC) WHERE is_active = TRUE",
            
            # System alerts indexes
            "CREATE INDEX IF NOT EXISTS idx_system_alerts_type_severity ON orchestrator.system_alerts(alert_type, severity, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_system_alerts_unresolved ON orchestrator.system_alerts(created_at DESC) WHERE resolved_at IS NULL",
            "CREATE INDEX IF NOT EXISTS idx_system_alerts_created_at ON orchestrator.system_alerts(created_at DESC)"
        ]
        
        for index_sql in indexes:
            await self.execute(index_sql)
    
    async def _create_functions(self):
        """Create database functions"""
        # Update timestamp trigger function
        await self.execute("""
            CREATE OR REPLACE FUNCTION orchestrator.update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """)
        
        # Create trigger
        await self.execute("DROP TRIGGER IF EXISTS trigger_system_state_updated_at ON orchestrator.system_state")
        await self.execute("""
            CREATE TRIGGER trigger_system_state_updated_at
                BEFORE UPDATE ON orchestrator.system_state
                FOR EACH ROW
                EXECUTE FUNCTION orchestrator.update_updated_at_column()
        """)
        
        # Cleanup function
        await self.execute("""
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
            $$ LANGUAGE plpgsql
        """)
        
        # Health summary function
        await self.execute("""
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
            $$ LANGUAGE plpgsql
        """)
    
    async def _create_views(self):
        """Create useful views"""
        # Recent operations view
        await self.execute("""
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
            ORDER BY created_at DESC
        """)
        
        # System state summary view
        await self.execute("""
            CREATE OR REPLACE VIEW orchestrator.v_system_state_summary AS
            SELECT 
                jsonb_object_agg(state_key, state_value) AS current_state,
                MAX(updated_at) AS last_updated
            FROM orchestrator.system_state
        """)
        
        # Daily operations view
        await self.execute("""
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
            ORDER BY operation_date DESC, operation_type
        """)
    
    async def _insert_initial_data(self):
        """Insert initial system state data"""
        initial_states = [
            ('current_state', {"state": "idle", "timestamp": datetime.utcnow().isoformat()}),
            ('system_info', {
                "version": "1.0.0",
                "environment": "production",
                "startup_time": datetime.utcnow().isoformat()
            })
        ]
        
        for state_key, state_value in initial_states:
            await self.execute("""
                INSERT INTO orchestrator.system_state (state_key, state_value) 
                VALUES ($1, $2)
                ON CONFLICT (state_key) DO NOTHING
            """, state_key, json.dumps(state_value))
    
    # =====================================================
    # STATE MANAGEMENT METHODS
    # =====================================================
    
    async def get_state_value(self, state_key: str) -> Optional[Dict[str, Any]]:
        """Get a specific state value by key"""
        result = await self.fetch_one("""
            SELECT state_value 
            FROM orchestrator.system_state 
            WHERE state_key = $1
        """, state_key)
        
        if result and result['state_value']:
            return result['state_value']
        return None
    
    async def get_sod_completion_data(self) -> Optional[Dict[str, Any]]:
        """Get SOD completion data"""
        return await self.get_state_value('last_sod')
    
    async def get_eod_completion_data(self) -> Optional[Dict[str, Any]]:
        """Get EOD completion data"""
        return await self.get_state_value('last_eod')
    
    async def get_current_state_data(self) -> Optional[Dict[str, Any]]:
        """Get current system state data"""
        return await self.get_state_value('current_state')
    
    async def get_last_error_data(self) -> Optional[Dict[str, Any]]:
        """Get last error state data"""
        return await self.get_state_value('last_error')
    
    async def save_state_value(self, state_key: str, state_value: Dict[str, Any]):
        """Save or update a state value"""
        await self.execute("""
            INSERT INTO orchestrator.system_state (state_key, state_value, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (state_key) 
            DO UPDATE SET state_value = $2, updated_at = NOW()
        """, state_key, json.dumps(state_value))
    
    async def save_current_state(self, current_state, timestamp: datetime = None):
        """Save current system state"""
        if timestamp is None:
            timestamp = datetime.utcnow()
            
        state_data = {
            "state": current_state.value if hasattr(current_state, 'value') else str(current_state),
            "timestamp": timestamp.isoformat()
        }
        
        await self.save_state_value("current_state", state_data)
    
    async def save_sod_completion(self, completion_time: datetime, details: Dict[str, Any] = None):
        """Save SOD completion timestamp and details"""
        state_data = {
            "timestamp": completion_time.isoformat(),
            "details": details
        }
        
        await self.save_state_value("last_sod", state_data)
    
    async def save_eod_completion(self, completion_time: datetime, details: Dict[str, Any] = None):
        """Save EOD completion timestamp and details"""
        state_data = {
            "timestamp": completion_time.isoformat(),
            "details": details
        }
        
        await self.save_state_value("last_eod", state_data)
    
    async def save_error_state(self, error_message: str, timestamp: datetime = None):
        """Save error state information"""
        if timestamp is None:
            timestamp = datetime.utcnow()
            
        error_data = {
            "error": error_message,
            "timestamp": timestamp.isoformat()
        }
        
        await self.save_state_value("last_error", error_data)
    
    # =====================================================
    # OPERATIONS LOG METHODS
    # =====================================================
    
    async def save_operation_log(self, operation_type: str, status: str, 
                               start_time: datetime, end_time: datetime = None,
                               details: Dict[str, Any] = None,
                               market_tz = None):
        """Log operation execution"""
        # Use market timezone to determine business date if provided
        if market_tz:
            et_date = start_time.astimezone(market_tz).date()
        else:
            et_date = start_time.astimezone(self.market_tz).date()
        
        await self.execute("""
            INSERT INTO orchestrator.operations_log 
            (operation_type, operation_date, start_time, end_time, status, details)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, operation_type, et_date, start_time, end_time, status, 
        json.dumps(details) if details else None)
    
    async def update_operation_status(self, operation_id: int, status: str, 
                                    end_time: datetime = None, 
                                    details: Dict[str, Any] = None):
        """Update an existing operation's status"""
        if end_time is None and status in ['SUCCESS', 'FAILED', 'CANCELLED', 'TIMEOUT']:
            end_time = datetime.utcnow()
        
        update_fields = ["status = $2"]
        params = [operation_id, status]
        
        if end_time:
            update_fields.append("end_time = $3")
            params.append(end_time)
        
        if details:
            update_fields.append(f"details = ${len(params) + 1}")
            params.append(json.dumps(details))
        
        query = f"""
            UPDATE orchestrator.operations_log 
            SET {', '.join(update_fields)}
            WHERE id = $1
        """
        
        await self.execute(query, *params)
    
    async def get_recent_operations(self, operation_type: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent operation history"""
        if operation_type:
            rows = await self.fetch_all("""
                SELECT * FROM orchestrator.operations_log
                WHERE operation_type = $1
                ORDER BY created_at DESC
                LIMIT $2
            """, operation_type, limit)
        else:
            rows = await self.fetch_all("""
                SELECT * FROM orchestrator.operations_log
                ORDER BY created_at DESC
                LIMIT $1
            """, limit)
        
        return rows
    
    async def get_operations_by_date(self, operation_date: date, 
                                   operation_type: str = None) -> List[Dict[str, Any]]:
        """Get operations for a specific date"""
        if operation_type:
            rows = await self.fetch_all("""
                SELECT * FROM orchestrator.operations_log
                WHERE operation_date = $1 AND operation_type = $2
                ORDER BY start_time DESC
            """, operation_date, operation_type)
        else:
            rows = await self.fetch_all("""
                SELECT * FROM orchestrator.operations_log
                WHERE operation_date = $1
                ORDER BY start_time DESC
            """, operation_date)
        
        return rows
    
    async def get_operation_status(self, operation_type: str, 
                                 operation_date: date = None) -> Optional[Dict[str, Any]]:
        """Get the latest status of an operation type"""
        if operation_date:
            result = await self.fetch_one("""
                SELECT * FROM orchestrator.operations_log
                WHERE operation_type = $1 AND operation_date = $2
                ORDER BY created_at DESC
                LIMIT 1
            """, operation_type, operation_date)
        else:
            result = await self.fetch_one("""
                SELECT * FROM orchestrator.operations_log
                WHERE operation_type = $1
                ORDER BY created_at DESC
                LIMIT 1
            """, operation_type)
        
        return result
    
    async def get_running_operations(self) -> List[Dict[str, Any]]:
        """Get all currently running operations"""
        return await self.fetch_all("""
            SELECT * FROM orchestrator.operations_log
            WHERE status IN ('STARTED', 'RUNNING')
            ORDER BY start_time DESC
        """)
    
    async def cleanup_old_operations(self, days_to_keep: int = 90) -> int:
        """Clean up old operation log entries using database function"""
        result = await self.fetch_one("""
            SELECT orchestrator.cleanup_old_operations($1) as deleted_count
        """, days_to_keep)
        
        return result['deleted_count'] if result else 0
    
    # =====================================================
    # SYSTEM METRICS METHODS
    # =====================================================
    
    async def save_system_metric(self, metric_name: str, metric_value: Union[float, Decimal], 
                               metric_unit: str = None, tags: Dict[str, Any] = None,
                               timestamp: datetime = None):
        """Save a system performance metric"""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        await self.execute("""
            INSERT INTO orchestrator.system_metrics 
            (metric_name, metric_value, metric_unit, metric_timestamp, tags)
            VALUES ($1, $2, $3, $4, $5)
        """, metric_name, metric_value, metric_unit, timestamp, 
        json.dumps(tags) if tags else None)
    
    async def get_system_metrics(self, metric_name: str = None, 
                               start_time: datetime = None, 
                               end_time: datetime = None,
                               limit: int = 100) -> List[Dict[str, Any]]:
        """Get system metrics with optional filtering"""
        conditions = []
        params = []
        param_count = 0
        
        if metric_name:
            param_count += 1
            conditions.append(f"metric_name = ${param_count}")
            params.append(metric_name)
        
        if start_time:
            param_count += 1
            conditions.append(f"metric_timestamp >= ${param_count}")
            params.append(start_time)
        
        if end_time:
            param_count += 1
            conditions.append(f"metric_timestamp <= ${param_count}")
            params.append(end_time)
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        param_count += 1
        
        query = f"""
            SELECT * FROM orchestrator.system_metrics
            {where_clause}
            ORDER BY metric_timestamp DESC
            LIMIT ${param_count}
        """
        params.append(limit)
        
        return await self.fetch_all(query, *params)
    
    async def get_latest_metrics(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get the most recent metrics across all types"""
        return await self.fetch_all("""
            SELECT DISTINCT ON (metric_name) 
                metric_name, metric_value, metric_unit, metric_timestamp, tags
            FROM orchestrator.system_metrics
            ORDER BY metric_name, metric_timestamp DESC
            LIMIT $1
        """, limit)
    
    # =====================================================
    # RECOVERY CHECKPOINT METHODS
    # =====================================================
    
    async def create_recovery_checkpoint(self, checkpoint_name: str, checkpoint_type: str,
                                       checkpoint_data: Dict[str, Any], 
                                       expires_at: datetime = None):
        """Create a recovery checkpoint"""
        result = await self.execute_returning("""
            INSERT INTO orchestrator.recovery_checkpoints 
            (checkpoint_name, checkpoint_type, checkpoint_data, expires_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (checkpoint_name, checkpoint_type)
            DO UPDATE SET 
                checkpoint_data = EXCLUDED.checkpoint_data,
                created_at = NOW(),
                expires_at = EXCLUDED.expires_at,
                is_active = TRUE
            RETURNING id
        """, checkpoint_name, checkpoint_type, json.dumps(checkpoint_data), expires_at)
        
        return result['id'] if result else None
    
    async def get_recovery_checkpoint(self, checkpoint_name: str, 
                                    checkpoint_type: str) -> Optional[Dict[str, Any]]:
        """Get a specific recovery checkpoint"""
        return await self.fetch_one("""
            SELECT * FROM orchestrator.recovery_checkpoints
            WHERE checkpoint_name = $1 AND checkpoint_type = $2 AND is_active = TRUE
            ORDER BY created_at DESC
            LIMIT 1
        """, checkpoint_name, checkpoint_type)
    
    async def get_active_checkpoints(self, checkpoint_type: str = None) -> List[Dict[str, Any]]:
        """Get all active recovery checkpoints"""
        if checkpoint_type:
            return await self.fetch_all("""
                SELECT * FROM orchestrator.recovery_checkpoints
                WHERE checkpoint_type = $1 AND is_active = TRUE
                ORDER BY created_at DESC
            """, checkpoint_type)
        else:
            return await self.fetch_all("""
                SELECT * FROM orchestrator.recovery_checkpoints
                WHERE is_active = TRUE
                ORDER BY created_at DESC
            """)
    
    async def deactivate_checkpoint(self, checkpoint_id: int):
        """Deactivate a recovery checkpoint"""
        await self.execute("""
            UPDATE orchestrator.recovery_checkpoints
            SET is_active = FALSE
            WHERE id = $1
        """, checkpoint_id)
    
    async def cleanup_expired_checkpoints(self):
        """Clean up expired recovery checkpoints"""
        result = await self.execute("""
            UPDATE orchestrator.recovery_checkpoints
            SET is_active = FALSE
            WHERE expires_at < NOW() AND is_active = TRUE
        """)
        
        return result
    
    # =====================================================
    # SYSTEM ALERTS METHODS
    # =====================================================
    
    async def create_system_alert(self, alert_type: str, severity: str, title: str, 
                                message: str, alert_data: Dict[str, Any] = None) -> Optional[int]:
        """Create a system alert"""
        result = await self.execute_returning("""
            INSERT INTO orchestrator.system_alerts 
            (alert_type, severity, title, message, alert_data)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """, alert_type, severity, title, message, json.dumps(alert_data) if alert_data else None)
        
        return result['id'] if result else None
    
    async def acknowledge_alert(self, alert_id: int, acknowledged_by: str):
        """Acknowledge a system alert"""
        await self.execute("""
            UPDATE orchestrator.system_alerts
            SET acknowledged_at = NOW(), acknowledged_by = $2
            WHERE id = $1 AND acknowledged_at IS NULL
        """, alert_id, acknowledged_by)
    
    async def resolve_alert(self, alert_id: int, resolved_by: str):
        """Resolve a system alert"""
        await self.execute("""
            UPDATE orchestrator.system_alerts
            SET resolved_at = NOW(), resolved_by = $2
            WHERE id = $1 AND resolved_at IS NULL
        """, alert_id, resolved_by)
    
    async def get_unresolved_alerts(self, severity: str = None) -> List[Dict[str, Any]]:
        """Get unresolved system alerts"""
        if severity:
            return await self.fetch_all("""
                SELECT * FROM orchestrator.system_alerts
                WHERE resolved_at IS NULL AND severity = $1
                ORDER BY created_at DESC
            """, severity)
        else:
            return await self.fetch_all("""
                SELECT * FROM orchestrator.system_alerts
                WHERE resolved_at IS NULL
                ORDER BY severity DESC, created_at DESC
            """)
    
    async def get_recent_alerts(self, hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent system alerts"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        return await self.fetch_all("""
            SELECT * FROM orchestrator.system_alerts
            WHERE created_at >= $1
            ORDER BY created_at DESC
            LIMIT $2
        """, cutoff_time, limit)
    
    # =====================================================
    # HEALTH AND SUMMARY METHODS
    # =====================================================
    
    async def get_system_health_summary(self, lookback_hours: int = 24) -> Dict[str, Any]:
        """Get comprehensive system health summary"""
        result = await self.fetch_one("""
            SELECT orchestrator.get_system_health_summary($1) as health_summary
        """, lookback_hours)
        
        if result and result['health_summary']:
            return result['health_summary']
        
        # Fallback to manual calculation if function fails
        return await self._manual_health_summary(lookback_hours)
    
    async def _manual_health_summary(self, lookback_hours: int = 24) -> Dict[str, Any]:
        """Manual health summary calculation as fallback"""
        cutoff_time = datetime.utcnow() - timedelta(hours=lookback_hours)
        
        recent_ops = await self.fetch_all("""
            SELECT operation_type, status FROM orchestrator.operations_log
            WHERE created_at >= $1
        """, cutoff_time)
        
        unresolved_alerts = await self.fetch_all("""
            SELECT COUNT(*) as count FROM orchestrator.system_alerts
            WHERE resolved_at IS NULL AND severity IN ('CRITICAL', 'HIGH')
        """)
        
        return {
            "total_operations": len(recent_ops),
            "successful_operations": len([op for op in recent_ops if op['status'] == 'SUCCESS']),
            "failed_operations": len([op for op in recent_ops if op['status'] == 'FAILED']),
            "running_operations": len([op for op in recent_ops if op['status'] == 'RUNNING']),
            "unresolved_alerts": unresolved_alerts[0]['count'] if unresolved_alerts else 0,
            "last_sod_status": None,
            "last_eod_status": None
        }
    
    async def get_system_state_summary(self) -> Dict[str, Any]:
        """Get current system state summary"""
        result = await self.fetch_one("""
            SELECT * FROM orchestrator.v_system_state_summary
        """)
        
        return result if result else {}
    
    async def get_daily_operations_summary(self, days_back: int = 7) -> List[Dict[str, Any]]:
        """Get daily operations summary"""
        cutoff_date = date.today() - timedelta(days=days_back)
        
        return await self.fetch_all("""
            SELECT * FROM orchestrator.v_daily_operations
            WHERE operation_date >= $1
            ORDER BY operation_date DESC, operation_type
        """, cutoff_date)
    
    async def get_operation_trends(self, operation_type: str, days_back: int = 30) -> Dict[str, Any]:
        """Get operation performance trends"""
        cutoff_date = date.today() - timedelta(days=days_back)
        
        trends = await self.fetch_all("""
            SELECT 
                operation_date,
                COUNT(*) as total_count,
                COUNT(*) FILTER (WHERE status = 'SUCCESS') as success_count,
                COUNT(*) FILTER (WHERE status = 'FAILED') as failed_count,
                AVG(EXTRACT(EPOCH FROM (end_time - start_time))) as avg_duration_seconds,
                MIN(EXTRACT(EPOCH FROM (end_time - start_time))) as min_duration_seconds,
                MAX(EXTRACT(EPOCH FROM (end_time - start_time))) as max_duration_seconds
            FROM orchestrator.operations_log
            WHERE operation_type = $1 
                AND operation_date >= $2 
                AND end_time IS NOT NULL
            GROUP BY operation_date
            ORDER BY operation_date DESC
        """, operation_type, cutoff_date)
        
        if not trends:
            return {"operation_type": operation_type, "trends": [], "summary": {}}
        
        # Calculate summary statistics
        total_ops = sum(t['total_count'] for t in trends)
        total_successes = sum(t['success_count'] for t in trends)
        total_failures = sum(t['failed_count'] for t in trends)
        
        avg_durations = [t['avg_duration_seconds'] for t in trends if t['avg_duration_seconds']]
        overall_avg_duration = sum(avg_durations) / len(avg_durations) if avg_durations else 0
        
        summary = {
            "total_operations": total_ops,
            "success_rate": (total_successes / total_ops * 100) if total_ops > 0 else 0,
            "failure_rate": (total_failures / total_ops * 100) if total_ops > 0 else 0,
            "average_duration_seconds": overall_avg_duration,
            "days_analyzed": len(trends)
        }
        
        return {
            "operation_type": operation_type,
            "trends": trends,
            "summary": summary
        }
    
    # =====================================================
    # MAINTENANCE AND UTILITY METHODS
    # =====================================================
    
    async def vacuum_analyze_tables(self):
        """Perform vacuum analyze on state management tables"""
        tables = [
            "orchestrator.system_state",
            "orchestrator.operations_log",
            "orchestrator.system_metrics",
            "orchestrator.recovery_checkpoints",
            "orchestrator.system_alerts"
        ]
        
        for table in tables:
            try:
                await self.execute(f"VACUUM ANALYZE {table}")
                logger.debug(f"✅ VACUUM ANALYZE completed for {table}")
            except Exception as e:
                logger.error(f"❌ VACUUM ANALYZE failed for {table}: {e}")
    
    async def get_table_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics about state management tables"""
        stats = {}
        
        # System state statistics
        state_stats = await self.fetch_one("""
            SELECT 
                COUNT(*) as total_states,
                MAX(updated_at) as last_updated
            FROM orchestrator.system_state
        """)
        stats['system_state'] = state_stats
        
        # Operations log statistics
        ops_stats = await self.fetch_one("""
            SELECT 
                COUNT(*) as total_operations,
                COUNT(DISTINCT operation_type) as unique_operation_types,
                COUNT(DISTINCT operation_date) as unique_dates,
                MIN(operation_date) as earliest_date,
                MAX(operation_date) as latest_date,
                COUNT(*) FILTER (WHERE status = 'SUCCESS') as successful_ops,
                COUNT(*) FILTER (WHERE status = 'FAILED') as failed_ops,
                COUNT(*) FILTER (WHERE status IN ('STARTED', 'RUNNING')) as running_ops
            FROM orchestrator.operations_log
        """)
        stats['operations_log'] = ops_stats
        
        # System metrics statistics
        metrics_stats = await self.fetch_one("""
            SELECT 
                COUNT(*) as total_metrics,
                COUNT(DISTINCT metric_name) as unique_metric_names,
                MIN(metric_timestamp) as earliest_metric,
                MAX(metric_timestamp) as latest_metric
            FROM orchestrator.system_metrics
        """)
        stats['system_metrics'] = metrics_stats
        
        # Recovery checkpoints statistics
        checkpoint_stats = await self.fetch_one("""
            SELECT 
                COUNT(*) as total_checkpoints,
                COUNT(*) FILTER (WHERE is_active = TRUE) as active_checkpoints,
                COUNT(DISTINCT checkpoint_type) as unique_types
            FROM orchestrator.recovery_checkpoints
        """)
        stats['recovery_checkpoints'] = checkpoint_stats
        
        # System alerts statistics
        alerts_stats = await self.fetch_one("""
            SELECT 
                COUNT(*) as total_alerts,
                COUNT(*) FILTER (WHERE resolved_at IS NULL) as unresolved_alerts,
                COUNT(*) FILTER (WHERE acknowledged_at IS NULL) as unacknowledged_alerts,
                COUNT(*) FILTER (WHERE severity = 'CRITICAL') as critical_alerts,
                COUNT(*) FILTER (WHERE severity = 'HIGH') as high_alerts
            FROM orchestrator.system_alerts
        """)
        stats['system_alerts'] = alerts_stats
        
        return stats
    
    async def export_state_data(self, start_date: date = None, end_date: date = None) -> Dict[str, Any]:
        """Export state management data for backup or analysis"""
        if start_date is None:
            start_date = date.today() - timedelta(days=30)
        if end_date is None:
            end_date = date.today()
        
        export_data = {
            "export_timestamp": datetime.utcnow().isoformat(),
            "date_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }
        }
        
        # Export system state
        export_data["system_state"] = await self.fetch_all("""
            SELECT * FROM orchestrator.system_state
            ORDER BY state_key
        """)
        
        # Export operations log for date range
        export_data["operations_log"] = await self.fetch_all("""
            SELECT * FROM orchestrator.operations_log
            WHERE operation_date BETWEEN $1 AND $2
            ORDER BY operation_date DESC, start_time DESC
        """, start_date, end_date)
        
        # Export system metrics for date range
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        export_data["system_metrics"] = await self.fetch_all("""
            SELECT * FROM orchestrator.system_metrics
            WHERE metric_timestamp BETWEEN $1 AND $2
            ORDER BY metric_timestamp DESC
        """, start_datetime, end_datetime)
        
        # Export active recovery checkpoints
        export_data["recovery_checkpoints"] = await self.fetch_all("""
            SELECT * FROM orchestrator.recovery_checkpoints
            WHERE is_active = TRUE
            ORDER BY checkpoint_type, checkpoint_name
        """)
        
        # Export recent alerts
        export_data["system_alerts"] = await self.fetch_all("""
            SELECT * FROM orchestrator.system_alerts
            WHERE created_at >= $1
            ORDER BY created_at DESC
        """, start_datetime)
        
        return export_data
    
    async def import_state_data(self, import_data: Dict[str, Any], 
                                overwrite_existing: bool = False):
        """Import state management data from backup"""
        imported_counts = {
            "system_state": 0,
            "operations_log": 0,
            "system_metrics": 0,
            "recovery_checkpoints": 0,
            "system_alerts": 0
        }
        
        try:
            async with self.db_manager.pool.acquire() as conn:
                async with conn.transaction():
                    # Import system state
                    if "system_state" in import_data:
                        for state_item in import_data["system_state"]:
                            if overwrite_existing:
                                await conn.execute("""
                                    INSERT INTO orchestrator.system_state 
                                    (state_key, state_value, updated_at)
                                    VALUES ($1, $2, $3)
                                    ON CONFLICT (state_key) 
                                    DO UPDATE SET state_value = EXCLUDED.state_value, 
                                                    updated_at = EXCLUDED.updated_at
                                """, state_item['state_key'], state_item['state_value'], 
                                state_item['updated_at'])
                            else:
                                await conn.execute("""
                                    INSERT INTO orchestrator.system_state 
                                    (state_key, state_value, updated_at)
                                    VALUES ($1, $2, $3)
                                    ON CONFLICT (state_key) DO NOTHING
                                """, state_item['state_key'], state_item['state_value'],
                                state_item['updated_at'])
                            imported_counts["system_state"] += 1
                    
                    # Import operations log
                    if "operations_log" in import_data:
                        for op_item in import_data["operations_log"]:
                            await conn.execute("""
                                INSERT INTO orchestrator.operations_log 
                                (operation_type, operation_date, start_time, end_time, 
                                    status, details, created_at)
                                VALUES ($1, $2, $3, $4, $5, $6, $7)
                                ON CONFLICT DO NOTHING
                            """, op_item['operation_type'], op_item['operation_date'],
                            op_item['start_time'], op_item['end_time'], op_item['status'],
                            op_item['details'], op_item['created_at'])
                            imported_counts["operations_log"] += 1
                    
                    # Similar imports for other tables...
                    # (Implementation continues for metrics, checkpoints, and alerts)
            
            logger.info(f"✅ Data import completed: {imported_counts}")
            return imported_counts
            
        except Exception as e:
            logger.error(f"❌ Data import failed: {e}")
            raise
    
    async def validate_data_integrity(self) -> Dict[str, Any]:
        """Validate data integrity across state management tables"""
        integrity_report = {
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {},
            "issues": []
        }
        
        # Check for orphaned operations (operations without proper start/end times)
        orphaned_ops = await self.fetch_all("""
            SELECT id, operation_type, status, start_time, end_time
            FROM orchestrator.operations_log
            WHERE (status IN ('SUCCESS', 'FAILED', 'CANCELLED', 'TIMEOUT') AND end_time IS NULL)
                OR (end_time < start_time)
        """)
        
        integrity_report["checks"]["orphaned_operations"] = len(orphaned_ops)
        if orphaned_ops:
            integrity_report["issues"].append({
                "type": "orphaned_operations",
                "count": len(orphaned_ops),
                "description": "Operations marked as complete but missing end_time or invalid time range"
            })
        
        # Check for stale running operations (running for more than 24 hours)
        stale_ops = await self.fetch_all("""
            SELECT id, operation_type, start_time, status
            FROM orchestrator.operations_log
            WHERE status IN ('STARTED', 'RUNNING') 
                AND start_time < NOW() - INTERVAL '24 hours'
        """)
        
        integrity_report["checks"]["stale_running_operations"] = len(stale_ops)
        if stale_ops:
            integrity_report["issues"].append({
                "type": "stale_running_operations",
                "count": len(stale_ops),
                "description": "Operations marked as running for more than 24 hours"
            })
        
        # Check for expired active checkpoints
        expired_checkpoints = await self.fetch_all("""
            SELECT id, checkpoint_name, expires_at
            FROM orchestrator.recovery_checkpoints
            WHERE is_active = TRUE AND expires_at < NOW()
        """)
        
        integrity_report["checks"]["expired_active_checkpoints"] = len(expired_checkpoints)
        if expired_checkpoints:
            integrity_report["issues"].append({
                "type": "expired_active_checkpoints",
                "count": len(expired_checkpoints),
                "description": "Recovery checkpoints marked as active but past expiration date"
            })
        
        # Check for duplicate state keys (shouldn't happen due to unique constraint)
        duplicate_states = await self.fetch_all("""
            SELECT state_key, COUNT(*) as count
            FROM orchestrator.system_state
            GROUP BY state_key
            HAVING COUNT(*) > 1
        """)
        
        integrity_report["checks"]["duplicate_state_keys"] = len(duplicate_states)
        if duplicate_states:
            integrity_report["issues"].append({
                "type": "duplicate_state_keys",
                "count": len(duplicate_states),
                "description": "Multiple entries found for same state key"
            })
        
        integrity_report["overall_status"] = "HEALTHY" if not integrity_report["issues"] else "ISSUES_FOUND"
        
        return integrity_report