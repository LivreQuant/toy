# source/core/state_manager.py
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class SimpleStateManager:
    """Simple state manager for orchestrator state"""

    def __init__(self):
        self.db_manager = None

    async def initialize(self, db_manager):
        """Initialize state manager"""
        self.db_manager = db_manager
        logger.info("📊 Simple state manager initialized")

    async def save_operation_log(self, operation: str, status: str,
                                 start_time: datetime, end_time: datetime = None,
                                 details: Dict[str, Any] = None):
        """Save operation log"""
        logger.info(f"📝 Operation log: {operation} - {status}")
        # Simple logging - could save to DB if needed

    async def save_sod_completion(self, completion_time: datetime, details: Dict[str, Any] = None):
        """Save SOD completion state"""
        logger.info(f"🌅 SOD completed at {completion_time}")
        # Could save to DB for recovery

    async def save_eod_completion(self, completion_time: datetime, details: Dict[str, Any] = None):
        """Save EOD completion state"""
        logger.info(f"🌙 EOD completed at {completion_time}")
        # Could save to DB for recovery