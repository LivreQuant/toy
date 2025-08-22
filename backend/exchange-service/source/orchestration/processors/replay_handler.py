# source/orchestration/processors/replay_coordinator.py
"""
Replay Coordinator - Handles replay mode orchestration
"""

import logging
from datetime import datetime
from typing import List, Optional, Deque
from collections import deque

from source.simulation.managers.equity import EquityBar
from source.simulation.managers.fx import FXRate


class ReplayCoordinator:
    """Coordinates replay mode operations"""

    def __init__(self, exchange_group_manager):
        self.exchange_group_manager = exchange_group_manager
        self.logger = logging.getLogger(self.__class__.__name__)

        # Queue for live data received during replay
        self.live_data_queue: Deque = deque()

    def handle_data_during_replay(self, equity_bars: List[EquityBar], fx: Optional[List[FXRate]]) -> bool:
        """
        Handle incoming live data when replay mode is active
        Returns True if data was queued, False if should process normally
        """
        if not hasattr(self.exchange_group_manager,
                       'is_replay_mode_active') or not self.exchange_group_manager.is_replay_mode_active():
            return False

        # Queue the live data
        timestamp = datetime.fromisoformat(equity_bars[0].timestamp) if equity_bars else datetime.now()
        self.live_data_queue.append({
            'timestamp': timestamp,
            'equity_bars': equity_bars,
            'fx': fx
        })

        queue_size = len(self.live_data_queue)
        self.logger.info(f"🎬 Replay mode active - queued live data (queue size: {queue_size})")

        return True

    def process_queued_data_after_replay(self, book_processor) -> None:
        """Process all queued live data after replay completes"""
        if not self.live_data_queue:
            self.logger.info("🎬 No queued data to process after replay")
            return

        queue_size = len(self.live_data_queue)
        self.logger.info(f"🎬 Processing {queue_size} queued data items after replay completion")

        books = self.exchange_group_manager.get_all_books()

        while self.live_data_queue:
            queued_item = self.live_data_queue.popleft()
            timestamp = queued_item['timestamp']
            equity_bars = queued_item['equity_bars']
            fx = queued_item['fx']

            self.logger.info(f"🎬 Processing queued data from {timestamp}")

            try:
                book_processor.process_books_sequentially(
                    books, equity_bars, fx, self.exchange_group_manager, is_backfill=False
                )

                # Update timing
                self.exchange_group_manager.last_snap_time = timestamp

            except Exception as e:
                self.logger.error(f"❌ Error processing queued data from {timestamp}: {e}")

        self.logger.info("🎬 All queued data processed after replay completion")
