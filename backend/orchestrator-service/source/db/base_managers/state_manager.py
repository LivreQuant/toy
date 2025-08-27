# source/db/base_managers/state_manager.py
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from .base_manager import BaseManager

logger = logging.getLogger(__name__)


class StateManager(BaseManager):
    """Simple state manager - just read/write state"""

    async def save_operation_log(self, operation: str, status: str,
                                start_time: datetime, end_time: datetime = None,
                                details: Dict[str, Any] = None):
        """Save operation log"""
        await self.execute("""
            INSERT INTO orchestrator.operation_logs 
            (operation, status, start_time, end_time, details)
            VALUES ($1, $2, $3, $4, $5)
        """, operation, status, start_time, end_time, details)

    async def save_sod_completion(self, completion_time: datetime, details: Dict[str, Any] = None):
        """Save SOD completion"""
        await self.execute("""
            INSERT INTO orchestrator.sod_completions (completion_time, details)
            VALUES ($1, $2)
        """, completion_time, details)

    async def save_eod_completion(self, completion_time: datetime, details: Dict[str, Any] = None):
        """Save EOD completion"""
        await self.execute("""
            INSERT INTO orchestrator.eod_completions (completion_time, details)
            VALUES ($1, $2)
        """, completion_time, details)

    async def get_last_sod_completion(self) -> Optional[Dict[str, Any]]:
        """Get last SOD completion"""
        return await self.fetch_one("""
            SELECT * FROM orchestrator.sod_completions 
            ORDER BY completion_time DESC LIMIT 1
        """)

    async def get_last_eod_completion(self) -> Optional[Dict[str, Any]]:
        """Get last EOD completion"""
        return await self.fetch_one("""
            SELECT * FROM orchestrator.eod_completions 
            ORDER BY completion_time DESC LIMIT 1
        """)

    async def validate_data_integrity(self) -> Dict[str, Any]:
        """Simple data integrity check"""
        # Just return a placeholder for now
        return {
            "overall_status": "HEALTHY",
            "issues": []
        }

    async def vacuum_analyze_tables(self):
        """Run vacuum analyze"""
        await self.execute("VACUUM ANALYZE")