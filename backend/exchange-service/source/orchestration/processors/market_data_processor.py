# source/orchestration/processors/market_data_processor.py
"""
Market Data Processor - Unified processor for multi-book exchange
Always handles a list of books, gap detection, and replay mode
"""
import logging
import time
from uuid import UUID
from datetime import datetime
from typing import List, Optional, Dict, Any

from source.simulation.core.models.models import EquityBar, FXRate
from source.utils.timezone_utils import to_iso_string
from source.orchestration.processors.book_processor import BookProcessor
from source.orchestration.processors.gap_handler import GapHandler


class MarketDataProcessor:
    """
    Unified market data processor that always handles multiple books
    (even if it's just one book) with gap detection and replay mode support
    """

    def __init__(self, exchange_group_manager):
        self.exchange_group_manager = exchange_group_manager
        self.logger = logging.getLogger(self.__class__.__name__)

        # Initialize components
        self.book_processor = BookProcessor()
        self.gap_handler = GapHandler(exchange_group_manager)

        books = exchange_group_manager.get_all_books()
        self.logger.info(f"🔧 MarketDataProcessor initialized for {len(books)} books: {books}")

    def process_market_data_bin(self, equity_bars: List[EquityBar], fx: Optional[List[FXRate]] = None,
                                bypass_replay_detection: bool = False):
        """
        Process market data for all books with session service notification.

        This is the MASTER ENTRY POINT for all market data processing.
        It orchestrates the entire flow including triggering session service callbacks.
        """
        processing_start_time = time.time()

        print(f"🔥🔥🔥 DEBUG: process_market_data_bin called")

        try:
            # Get books and validate
            books = self.exchange_group_manager.get_all_books()
            print(f"🔥🔥🔥 DEBUG: books = {books} (count: {len(books)})")
            print(f"🔥🔥🔥 DEBUG: equity_bars count = {len(equity_bars) if equity_bars else 0}")
            print(f"🔥🔥🔥 DEBUG: bypass_replay_detection = {bypass_replay_detection}")

            if not books:
                self.logger.warning("⚠️ No books found in exchange group manager")
                return

            if not equity_bars:
                self.logger.debug("📊 No equity bars to process - skipping")
                return

            # Extract timestamps for logging
            incoming_market_time = datetime.fromisoformat(equity_bars[0].timestamp)
            last_market_time = self.exchange_group_manager.last_snap_time

            self.logger.info("=" * 120)
            self.logger.info(f"🔄 MARKET DATA BIN PROCESSING STARTED")
            self.logger.info(f"📊 Processing {len(equity_bars)} equity bars, {len(fx) if fx else 0} FX rates")
            self.logger.info(f"👥 books: {len(books)}")
            self.logger.info(f"⏰ Incoming time: {incoming_market_time}")
            self.logger.info(f"🕐 Last snap: {last_market_time}")
            self.logger.info(f"🎬 Bypass replay: {bypass_replay_detection}")
            self.logger.info("=" * 120)

            # Check for replay mode (unless bypassed)
            if not bypass_replay_detection:
                if hasattr(self.exchange_group_manager, 'unified_replay_manager') and self.exchange_group_manager.unified_replay_manager and self.exchange_group_manager.unified_replay_manager.is_in_replay_mode():
                    self.logger.info("🎬 Replay mode active - data will be queued")
                    return

                # Handle gaps and replay mode
                gap_handled = self.gap_handler.handle_gaps_and_replay(
                    incoming_market_time, last_market_time, equity_bars, fx
                )

                # If gap handler didn't process the data, process it normally
                if not gap_handled:
                    self._process_current_data(books, equity_bars, fx, incoming_market_time)
            else:
                # Process data directly (replay/backfill mode)
                self._process_current_data(books, equity_bars, fx, incoming_market_time, is_backfill=True)

            # Update last snap time with database persistence
            self.exchange_group_manager.update_last_snap_time(incoming_market_time)

            total_duration = (time.time() - processing_start_time) * 1000
            self.logger.info("=" * 120)
            self.logger.info(f"✅ MARKET DATA PROCESSING COMPLETE in {total_duration:.2f}ms")
            self.logger.info("=" * 120)

        except Exception as e:
            self.logger.error(f"❌ Error in market data processing: {e}", exc_info=True)
            raise

    def _process_current_data(self, books: List[UUID], equity_bars: List[EquityBar],
                              fx: Optional[List[FXRate]], market_time: datetime,
                              is_backfill: bool = False):
        """Process current market data for all books"""
        try:
            mode = "BACKFILL" if is_backfill else "LIVE"
            self.logger.info(f"📊 Processing {mode} data for {len(books)} books at {market_time}")

            # Process for each book
            self.book_processor.process_books_sequentially(
                books, equity_bars, fx, self.exchange_group_manager, is_backfill
            )

            self.logger.info(f"✅ {mode} data processing complete for all books")

        except Exception as e:
            self.logger.error(f"❌ Error processing {mode} data: {e}", exc_info=True)
            raise

    def get_processing_stats(self) -> Dict[str, Any]:
        """Get statistics about market data processing"""
        return {
            'total_books': len(self.exchange_group_manager.get_all_books()),
            'last_snap_time': to_iso_string(self.exchange_group_manager.last_snap_time),
            'replay_status': self.gap_handler.get_replay_status() if self.gap_handler else None
        }

    def process_replay_data(self, equity_bars: List[EquityBar], fx: Optional[List[FXRate]] = None) -> None:
        """Process data specifically for replay mode"""
        try:
            if not equity_bars:
                return

            books = self.exchange_group_manager.get_all_books()
            timestamp = datetime.fromisoformat(equity_bars[0].timestamp)

            self.logger.info(f"🎬 Processing replay data for {timestamp}")
            self.book_processor.process_books_sequentially(
                books, equity_bars, fx, self.exchange_group_manager, is_backfill=True
            )

            from source.utils.timezone_utils import ensure_utc
            self.exchange_group_manager.update_last_snap_time(ensure_utc(timestamp))

        except Exception as e:
            self.logger.error(f"❌ Error processing replay data: {e}")
            raise