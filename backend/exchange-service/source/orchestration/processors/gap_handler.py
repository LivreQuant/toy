# source/orchestration/processors/gap_handler.py
"""
Gap Handler - Simple gap detection and replay mode activation
A gap is a gap. Missing 1 minute = replay mode.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from source.simulation.core.models.models import EquityBar, FXRate


class GapHandler:
    """Simple gap detection - any missing minute triggers replay mode"""

    def __init__(self, exchange_group_manager):
        self.exchange_group_manager = exchange_group_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    def handle_gaps_and_replay(self, incoming_market_time: datetime, last_market_time: datetime,
                               equity_bars: List[EquityBar], fx: Optional[List[FXRate]]) -> bool:
        """
        Handle gaps - any gap triggers replay mode
        Returns True if replay mode was activated, False if no gap
        """
        if not last_market_time:
            self.logger.info("🔄 No previous market time - processing normally")
            return False

        # Calculate expected next time (1 minute after last)
        expected_next_time = last_market_time + timedelta(minutes=1)

        # Check if we have a gap (incoming time is not the expected next time)
        if incoming_market_time != expected_next_time:
            gap_duration = incoming_market_time - last_market_time
            self.logger.warning(f"🕳️ GAP DETECTED: Expected {expected_next_time}, got {incoming_market_time}")
            self.logger.warning(f"🕳️ Gap duration: {gap_duration}")

            # Activate replay mode
            return self._activate_replay_mode(last_market_time, incoming_market_time, equity_bars, fx)

        # No gap - process normally
        self.logger.debug("✅ No gap detected - processing normally")
        return False

    def _activate_replay_mode(self, last_market_time: datetime, incoming_market_time: datetime,
                              equity_bars: List[EquityBar], fx: Optional[List[FXRate]]) -> bool:
        """Activate replay mode to fill the gap"""
        self.logger.info("🎬 ACTIVATING REPLAY MODE")

        try:
            # Try to activate replay mode through exchange group manager
            if hasattr(self.exchange_group_manager, 'activate_replay_mode'):
                success = self.exchange_group_manager.activate_replay_mode(
                    gap_start=last_market_time,
                    gap_end=incoming_market_time,
                    current_live_data={'equity_bars': equity_bars, 'fx': fx}
                )

                if success:
                    self.logger.info("🎬 Replay mode activated successfully")
                    return True
                else:
                    self.logger.error("❌ Failed to activate replay mode")

            # Alternative method
            elif hasattr(self.exchange_group_manager, 'process_market_data_with_replay_awareness'):
                success = self.exchange_group_manager.process_market_data_with_replay_awareness(
                    equity_bars, fx
                )

                if success:
                    self.logger.info("🎬 Replay mode activated via awareness method")
                    return True

            # No replay mode available
            self.logger.error("❌ No replay mode methods available - gap cannot be filled")
            return False

        except Exception as e:
            self.logger.error(f"❌ Error activating replay mode: {e}")
            return False
