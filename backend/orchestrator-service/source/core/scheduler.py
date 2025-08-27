# source/core/scheduler.py
import logging
from datetime import datetime, time
import pytz

logger = logging.getLogger(__name__)


class SimpleScheduler:
    """Simple scheduler for SOD/EOD operations"""

    def __init__(self, orchestrator):
        self.config = get_config()
        self.orchestrator = orchestrator
        self.market_tz = pytz.timezone(self.config.MARKET_TIMEZONE)
        
        # Use config times
        self.sod_time = self.config.sod_time
        self.eod_time = self.config.eod_time

    async def check_schedule(self):
        """Check if it's time to run SOD or EOD"""
        now_et = datetime.now(self.market_tz)
        current_time = now_et.time()

        # Skip weekends
        if now_et.weekday() >= 5:
            return

        # Check if it's SOD time
        if (current_time >= self.sod_time and
                current_time < time(7, 0) and  # 1-hour window
                not self.orchestrator.sod_complete):
            logger.info("⏰ SOD time reached")
            await self.orchestrator.trigger_sod_operations()

        # Check if it's EOD time
        elif (current_time >= self.eod_time and
              current_time < time(19, 0) and  # 1-hour window
              self.orchestrator.sod_complete and
              not self.orchestrator.eod_complete):
            logger.info("⏰ EOD time reached")
            await self.orchestrator.trigger_eod_operations()