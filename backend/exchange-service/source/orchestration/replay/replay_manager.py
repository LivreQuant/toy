# source/orchestration/replay/replay_manager.py
"""
Unified replay and gap detection manager - refactored into manageable modules
"""

import logging
from datetime import datetime
from typing import Optional, Callable, List, Tuple

from .replay_types import ReplayModeState, ReplayProgress
from .gap_detector import GapDetector
from .data_loader import DataLoader
from .replay_engine import ReplayEngine
from .replay_utils import ReplayUtils
from source.simulation.managers.equity import EquityBar
from source.simulation.managers.fx import FXRate
from source.orchestration.processors.market_data_processor import MarketDataProcessor


class ReplayManager:
    """
    Unified replay and gap detection manager that handles:
    - Gap detection between market timestamps
    - Replay mode for catching up missing data
    - File loading from both CSV (bin snaps) and JSON (backfill data)
    - Data conversion and processing
    - Threading and state management
    - Graceful transition back to live mode
    """

    def __init__(self, exchange_group_manager, market_data_client=None,
                 polling_interval: int = 5, max_backfill_days: int = 7):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.exchange_group_manager = exchange_group_manager
        self.market_data_client = market_data_client
        self.polling_interval = polling_interval
        self.max_backfill_days = max_backfill_days

        # Initialize component modules
        self.gap_detector = GapDetector()
        self.data_loader = DataLoader()
        self.replay_engine = ReplayEngine(
            exchange_group_manager=exchange_group_manager,
            market_data_processor=MarketDataProcessor(exchange_group_manager),
            polling_interval=polling_interval
        )
        self.utils = ReplayUtils()

        self.logger.info("🎬 Unified Replay Manager initialized")
        self.logger.info(f"🔄 Polling interval: {self.polling_interval} seconds")
        self.logger.info(f"⏰ Max backfill period: {self.max_backfill_days} days")
        self.logger.info(f"🚫 Computer time: IGNORED - only market timestamps used")

    # ===================================================================================
    # GAP DETECTION FUNCTIONALITY
    # ===================================================================================

    def detect_gap(self, last_market_time: datetime, incoming_market_time: datetime) -> Optional[Tuple[datetime, datetime]]:
        """
        Detect if there's a gap between MARKET timestamps only.
        Returns (gap_start, gap_end) if there are missing bins, None otherwise.
        Normal 1-minute progression (60 seconds) should NOT trigger replay mode.
        """
        return self.gap_detector.detect_gap(last_market_time, incoming_market_time)

    def load_missing_data(self, gap_start: datetime, gap_end: datetime) -> List[Tuple[datetime, List[EquityBar], Optional[List[FXRate]]]]:
        """
        Load missing equity and FX data from the data directory for the MARKET gap period.
        Returns list of (market_timestamp, equity_bars, fx) tuples.
        Supports both CSV (bin snap) and JSON (backfill) formats.
        """
        return self.data_loader.load_missing_data(gap_start, gap_end)

    # ===================================================================================
    # REPLAY MODE FUNCTIONALITY
    # ===================================================================================

    def enter_replay_mode(self, last_snap_time: datetime, target_live_time: datetime) -> None:
        """Enter replay mode to catch up missing bin snaps"""
        self.replay_engine.enter_replay_mode(last_snap_time, target_live_time)

    def update_latest_live_timestamp(self, timestamp: datetime) -> None:
        """Update the latest live data timestamp"""
        self.replay_engine.update_latest_live_timestamp(timestamp)

    def stop_replay(self) -> None:
        """Stop replay mode"""
        self.replay_engine.stop_replay()

    def get_replay_status(self) -> dict:
        """Get current replay status"""
        return self.replay_engine.get_replay_status()

    def is_in_replay_mode(self) -> bool:
        """Check if currently in replay mode"""
        return self.replay_engine.is_in_replay_mode()

    def get_available_bin_snaps(self) -> List[str]:
        """Get list of available bin snap files in data directory"""
        return self.utils.get_available_bin_snaps()

    # ===================================================================================
    # CALLBACK MANAGEMENT
    # ===================================================================================

    @property
    def on_replay_complete(self) -> Optional[Callable]:
        """Get replay completion callback"""
        return self.replay_engine.on_replay_complete

    @on_replay_complete.setter
    def on_replay_complete(self, callback: Optional[Callable]) -> None:
        """Set replay completion callback"""
        self.replay_engine.on_replay_complete = callback

    @property
    def on_replay_progress(self) -> Optional[Callable[[ReplayProgress], None]]:
        """Get replay progress callback"""
        return self.replay_engine.on_replay_progress

    @on_replay_progress.setter
    def on_replay_progress(self, callback: Optional[Callable[[ReplayProgress], None]]) -> None:
        """Set replay progress callback"""
        self.replay_engine.on_replay_progress = callback

    # ===================================================================================
    # STATE PROPERTIES (WITH SETTERS FOR BACKWARD COMPATIBILITY)
    # ===================================================================================

    @property
    def state(self) -> ReplayModeState:
        """Get current replay state"""
        return self.replay_engine.state

    @state.setter
    def state(self, new_state: ReplayModeState) -> None:
        """Set replay state (for backward compatibility)"""
        self.logger.info(f"🎬 External state change: {self.replay_engine.state.value} -> {new_state.value}")
        self.replay_engine.state = new_state

    @property
    def current_progress(self) -> Optional[ReplayProgress]:
        """Get current replay progress"""
        return self.replay_engine.current_progress

    @property
    def latest_live_timestamp(self) -> Optional[datetime]:
        """Get latest live timestamp"""
        return self.replay_engine.latest_live_timestamp

    # ===================================================================================
    # ADDITIONAL COMPATIBILITY PROPERTIES
    # ===================================================================================

    @property
    def replay_thread(self):
        """Get replay thread (for backward compatibility)"""
        return self.replay_engine.replay_thread

    @property
    def stop_event(self):
        """Get stop event (for backward compatibility)"""
        return self.replay_engine.stop_event

    # ===================================================================================
    # UNIFIED INTERFACE METHODS
    # ===================================================================================

    def check_and_handle_market_data_gap(self, incoming_market_time: datetime) -> Optional[Tuple[datetime, datetime]]:
        """
        Unified method to check for gaps and return gap info if found.
        This replaces the separate gap detection methods.
        """
        try:
            self.logger.info("🔍 DEBUG: check_and_handle_market_data_gap called")

            last_market_time = self.exchange_group_manager.last_snap_time
            self.logger.info(f"🔍 DEBUG: last_market_time = {last_market_time}")
            self.logger.info(f"🔍 DEBUG: incoming_market_time = {incoming_market_time}")

            result = self.detect_gap(last_market_time, incoming_market_time)
            self.logger.info(f"🔍 DEBUG: detect_gap returned = {result}")

            return result
        except Exception as e:
            self.logger.error(f"❌ Error in check_and_handle_market_data_gap: {e}")
            import traceback
            self.logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return None

    def load_missing_market_data(self, gap_start: datetime, gap_end: datetime) -> List[Tuple[datetime, List[EquityBar], Optional[List[FXRate]]]]:
        """
        Unified method to load missing market data.
        This replaces the separate loading methods.
        """
        return self.load_missing_data(gap_start, gap_end)

    def process_backfill_data(self, missing_data: List[Tuple[datetime, List[EquityBar], Optional[List[FXRate]]]]) -> None:
        """
        Process backfill data for gap filling WITH session service updates.
        """
        self.logger.info(f"🔄 Processing {len(missing_data)} backfill data points")
        self.logger.info("🎬 SESSION SERVICE WILL RECEIVE REPLAY UPDATES")

        for i, (timestamp, equity_bars, fx_rates) in enumerate(missing_data):
            try:
                self.logger.info(f"🔄 Processing backfill data {i + 1}/{len(missing_data)} for {timestamp}")

                # Use bypass flag to avoid replay detection during backfill
                # BUT still trigger session service callbacks
                self.replay_engine.market_data_processor.process_market_data_bin(
                    equity_bars, fx_rates, bypass_replay_detection=True
                )

                # Update last snap time
                self.exchange_group_manager.last_snap_time = timestamp

                # Log progress for session service
                if i % 10 == 0 or i == len(missing_data) - 1:
                    self.logger.info(f"🎬 Replay progress: {i + 1}/{len(missing_data)} - Session service receiving updates")

            except Exception as e:
                self.logger.error(f"❌ Error processing backfill data for {timestamp}: {e}")

        self.logger.info("✅ Backfill processing complete - Session service received all replay updates")

    def is_replay_mode_active(self) -> bool:
        """Check if replay mode is currently active"""
        return self.is_in_replay_mode()

    def get_status(self) -> dict:
        """Get comprehensive status of both gap detection and replay functionality"""
        return {
            'replay_status': self.get_replay_status(),
            'max_backfill_days': self.max_backfill_days,
            'polling_interval': self.polling_interval,
            'available_bin_snaps': len(self.get_available_bin_snaps()),
            'latest_live_timestamp': self.latest_live_timestamp.isoformat() if self.latest_live_timestamp else None
        }
