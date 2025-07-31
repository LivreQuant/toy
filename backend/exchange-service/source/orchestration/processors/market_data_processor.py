# source/orchestration/processors/market_data_processor.py
"""
Market Data Processor - Unified processor for multi-user exchange
Always handles a list of users, gap detection, and replay mode
"""

import logging
import time
import asyncio
from datetime import datetime
from typing import List, Optional

from source.simulation.managers.equity import EquityBar
from source.simulation.managers.fx import FXRate
from source.utils.timezone_utils import ensure_timezone_aware
from .user_processor import UserProcessor
from .gap_handler import GapHandler


class MarketDataProcessor:
    """
    Unified market data processor that always handles multiple users
    (even if it's just one user) with gap detection and replay mode support
    """

    def __init__(self, exchange_group_manager):
        self.exchange_group_manager = exchange_group_manager
        self.logger = logging.getLogger(self.__class__.__name__)

        # Initialize components
        self.user_processor = UserProcessor()
        self.gap_handler = GapHandler(exchange_group_manager)

        users = exchange_group_manager.get_all_users()
        self.logger.info(f"🔧 MarketDataProcessor initialized for {len(users)} users: {users}")

    def process_market_data_bin(self, equity_bars: List[EquityBar], fx: Optional[List[FXRate]] = None,
                                bypass_replay_detection: bool = False) -> None:
        """
        Process market data for all users with gap detection and replay mode support

        Args:
            equity_bars: List of equity market data bars
            fx: Optional list of FX rates
            bypass_replay_detection: If True, skip gap detection and process directly (used by replay mode)
        """
        processing_start_time = time.time()

        try:
            if not equity_bars:
                self.logger.debug("📊 Empty equity data - likely health check")
                return

            users = self.exchange_group_manager.get_all_users()
            if not users:
                self.logger.error("❌ No users found for processing")
                return

            incoming_market_time = ensure_timezone_aware(datetime.fromisoformat(equity_bars[0].timestamp))
            last_market_time = ensure_timezone_aware(self.exchange_group_manager.last_snap_time)

            self.logger.info("=" * 120)
            self.logger.info(f"🚀 PROCESSING MARKET DATA FOR {len(users)} USERS")
            self.logger.info("=" * 120)
            self.logger.info(f"📊 Equity Bars: {len(equity_bars)}")
            self.logger.info(f"📊 FX Rates: {len(fx) if fx else 0}")
            self.logger.info(f"⏰ Incoming Time: {incoming_market_time}")
            self.logger.info(f"⏰ Last Market Time: {last_market_time}")

            if bypass_replay_detection:
                self.logger.info("🔄 Bypass replay detection enabled - processing directly")

            # If bypass flag is set (replay mode), skip all gap detection
            if bypass_replay_detection:
                self._process_current_data(users, equity_bars, fx, incoming_market_time)
                self.exchange_group_manager.update_last_snap_time(incoming_market_time)

                total_duration = (time.time() - processing_start_time) * 1000
                self.logger.info(f"✅ BYPASS MODE PROCESSING COMPLETE in {total_duration:.2f}ms")
                return

            # Check if replay mode is active
            if hasattr(self.exchange_group_manager, 'is_replay_mode_active') and self.exchange_group_manager.is_replay_mode_active():
                self.logger.info("🎬 Replay mode active - data will be queued")
                return

            # Handle gaps and replay mode
            gap_handled = self.gap_handler.handle_gaps_and_replay(
                incoming_market_time, last_market_time, equity_bars, fx, users
            )

            # If gap handler didn't process the data, process it normally
            if not gap_handled:
                self._process_current_data(users, equity_bars, fx, incoming_market_time)

            # ============================================================================
            # ALL USER PROCESSING IS COMPLETE - NOW UPDATE LAST_SNAP WITH DATABASE PERSISTENCE
            # ============================================================================
            self.exchange_group_manager.update_last_snap_time(incoming_market_time)

            total_duration = (time.time() - processing_start_time) * 1000
            self.logger.info("=" * 120)
            self.logger.info(f"✅ MARKET DATA PROCESSING COMPLETE in {total_duration:.2f}ms")
            self.logger.info("=" * 120)

        except Exception as e:
            total_duration = (time.time() - processing_start_time) * 1000
            self.logger.error("=" * 120)
            self.logger.error(f"❌ MARKET DATA PROCESSING FAILED after {total_duration:.2f}ms: {e}")
            self.logger.error("=" * 120)
            raise

    def _process_current_data(self, users: List[str], equity_bars: List[EquityBar],
                              fx: Optional[List[FXRate]], incoming_market_time: datetime):
        """Process current market data for all users"""
        self.logger.info(f"🔄 Processing current data for {incoming_market_time}")
        self.user_processor.process_users_sequentially(
            users, equity_bars, fx, self.exchange_group_manager, is_backfill=False
        )

    def process_replay_data(self, equity_bars: List[EquityBar], fx: Optional[List[FXRate]] = None) -> None:
        """Process data specifically for replay mode"""
        try:
            if not equity_bars:
                return

            users = self.exchange_group_manager.get_all_users()
            timestamp = datetime.fromisoformat(equity_bars[0].timestamp)

            self.logger.info(f"🎬 Processing replay data for {timestamp}")
            self.user_processor.process_users_sequentially(
                users, equity_bars, fx, self.exchange_group_manager, is_backfill=True
            )

            from source.utils.timezone_utils import ensure_utc
            self.exchange_group_manager.update_last_snap_time(ensure_utc(timestamp))

        except Exception as e:
            self.logger.error(f"❌ Error processing replay data: {e}")
            raise