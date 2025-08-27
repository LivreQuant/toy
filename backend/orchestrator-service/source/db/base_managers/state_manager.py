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
                                 market_tz=None):
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
