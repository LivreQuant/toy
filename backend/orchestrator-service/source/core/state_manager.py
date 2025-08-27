# source/core/state_manager.py
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any
import pytz

logger = logging.getLogger(__name__)


class StateManager:
    """Manages system state persistence and recovery with proper UTC handling"""

    def __init__(self):
        self.db_state_manager = None
        self.market_tz = pytz.timezone('America/New_York')

        # State tracking (all in UTC)
        self.last_sod_time: Optional[datetime] = None
        self.last_eod_time: Optional[datetime] = None
        self.current_state_data: Dict[str, Any] = {}

    async def initialize(self, db_manager):
        """Initialize state manager with database connection"""
        self.db_state_manager = db_manager.state
        await self.db_state_manager.initialize_tables()
        logger.info("🗄️ State manager initialized")

    async def load_current_state(self) -> Dict[str, Any]:
        """Load current system state from database and return recovery info"""
        try:
            # Load last SOD/EOD times (stored in UTC)
            sod_data = await self.db_state_manager.get_sod_completion_data()
            eod_data = await self.db_state_manager.get_eod_completion_data()

            if sod_data and sod_data.get('timestamp'):
                self.last_sod_time = datetime.fromisoformat(sod_data['timestamp'])

            if eod_data and eod_data.get('timestamp'):
                self.last_eod_time = datetime.fromisoformat(eod_data['timestamp'])

            # Determine current state based on what happened today (in ET business date)
            now_utc = datetime.utcnow().replace(tzinfo=pytz.UTC)
            now_et = now_utc.astimezone(self.market_tz)
            today_et = now_et.date()

            recovery_info = self._determine_recovery_state(today_et, now_utc)

            logger.info(f"📊 State loaded - Last SOD: {self.last_sod_time}, Last EOD: {self.last_eod_time}")
            logger.info(f"🔄 Recovery info: {recovery_info}")

            return recovery_info

        except Exception as e:
            logger.error(f"❌ Failed to load current state: {e}", exc_info=True)
            return {"sod_complete": False, "eod_complete": False}

    def _determine_recovery_state(self, today_et: date, now_utc: datetime) -> Dict[str, Any]:
        """Determine what state we should be in based on completed operations"""
        recovery_info = {
            "sod_complete": False,
            "eod_complete": False,
            "should_be_trading": False,
            "should_be_idle": False
        }

        # Check if SOD ran today
        if (self.last_sod_time and
                self.last_sod_time.astimezone(self.market_tz).date() == today_et):
            recovery_info["sod_complete"] = True
            recovery_info["should_be_trading"] = True
            logger.info(f"✅ SOD completed today at {self.last_sod_time}")

        # Check if EOD ran today  
        if (self.last_eod_time and
                self.last_eod_time.astimezone(self.market_tz).date() == today_et):
            recovery_info["eod_complete"] = True
            recovery_info["should_be_idle"] = True
            recovery_info["should_be_trading"] = False  # EOD overrides SOD
            logger.info(f"✅ EOD completed today at {self.last_eod_time}")

        return recovery_info

    async def save_current_state(self, current_state):
        """Save current system state (in UTC)"""
        try:
            await self.db_state_manager.save_current_state(current_state)
            logger.debug(f"💾 Current state saved: {current_state.value}")
        except Exception as e:
            logger.error(f"❌ Failed to save current state: {e}", exc_info=True)

    async def save_operation_log(self, operation_type: str, status: str,
                                 start_time: datetime, end_time: datetime = None,
                                 details: Dict[str, Any] = None):
        """Log operation execution (all times in UTC, but use ET business date)"""
        try:
            await self.db_state_manager.save_operation_log(
                operation_type, status, start_time, end_time, details, self.market_tz
            )

            et_date = start_time.astimezone(self.market_tz).date()
            logger.debug(f"📝 Operation logged: {operation_type} - {status} (ET date: {et_date})")
        except Exception as e:
            logger.error(f"❌ Failed to save operation log: {e}", exc_info=True)

    async def save_sod_completion(self, completion_time: datetime, details: Dict[str, Any] = None):
        """Save SOD completion timestamp (in UTC)"""
        try:
            self.last_sod_time = completion_time
            await self.db_state_manager.save_sod_completion(completion_time, details)

            et_time = completion_time.astimezone(self.market_tz)
            logger.info(f"✅ SOD completion saved: {et_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        except Exception as e:
            logger.error(f"❌ Failed to save SOD completion: {e}", exc_info=True)

    async def save_eod_completion(self, completion_time: datetime, details: Dict[str, Any] = None):
        """Save EOD completion timestamp (in UTC)"""
        try:
            self.last_eod_time = completion_time
            await self.db_state_manager.save_eod_completion(completion_time, details)

            et_time = completion_time.astimezone(self.market_tz)
            logger.info(f"✅ EOD completion saved: {et_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        except Exception as e:
            logger.error(f"❌ Failed to save EOD completion: {e}", exc_info=True)

    async def get_recent_operations(self, operation_type: str = None, limit: int = 10):
        """Get recent operation history"""
        try:
            return await self.db_state_manager.get_recent_operations(operation_type, limit)
        except Exception as e:
            logger.error(f"❌ Failed to get recent operations: {e}", exc_info=True)
            return []

    async def save_error_state(self, error_message: str):
        """Save error state information"""
        try:
            await self.db_state_manager.save_error_state(error_message)
            logger.error(f"💾 Error state saved: {error_message}")
        except Exception as e:
            logger.error(f"❌ Failed to save error state: {e}", exc_info=True)

    async def get_system_health_summary(self) -> Dict[str, Any]:
        """Get system health summary"""
        try:
            return await self.db_state_manager.get_system_health_summary()
        except Exception as e:
            logger.error(f"❌ Failed to get system health summary: {e}", exc_info=True)
            return {}
