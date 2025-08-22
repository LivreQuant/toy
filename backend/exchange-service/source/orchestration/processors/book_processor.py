# source/orchestration/processors/book_processor.py
"""
book Processor - Handles processing data for all books
"""

import logging
import traceback
from datetime import datetime
from typing import List, Optional

from source.simulation.core.models.models import EquityBar, FXRate
from .processing_steps import ProcessingSteps


class BookProcessor:
    """Handles processing market data for all books"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.processing_steps = ProcessingSteps()

    def process_books_sequentially(self, books: List[str], equity_bars: List[EquityBar],
                                   fx: Optional[List[FXRate]], exchange_group_manager,
                                   is_backfill: bool = False) -> None:
        """Process market data for all books sequentially"""
        print(f"🔥🔥🔥 ENTERING process_books_sequentially")
        print(f"🔥🔥🔥 books = {books}")
        print(f"🔥🔥🔥 equity_bars count = {len(equity_bars) if equity_bars else 0}")
        print(f"🔥🔥🔥 is_backfill = {is_backfill}")

        successful_books = 0
        failed_books = 0

        prefix = "🔄 BACKFILL" if is_backfill else "🔥 LIVE"
        self.logger.info(f"{prefix} - Processing {len(books)} books sequentially...")

        # Process each book
        for book_id in books:
            print(f"🔥🔥🔥 Processing book {book_id}")
            try:
                if book_id not in exchange_group_manager.book_contexts:
                    print(f"🔥🔥🔥 book {book_id} NOT IN CONTEXTS!")
                    self.logger.error(f"❌ book {book_id} not found in book contexts")
                    failed_books += 1
                    continue

                book_context = exchange_group_manager.book_contexts[book_id]
                print(f"🔥🔥🔥 Got book context for {book_id}")
                self.logger.info(f"{prefix} - Processing book {book_id}...")

                self._process_single_book(book_context, equity_bars, fx)
                successful_books += 1
                print(f"🔥🔥🔥 book {book_id} processed successfully")
                self.logger.info(f"{prefix} - ✅ book {book_id} processed successfully")

            except Exception as e:
                print(f"🔥🔥🔥 EXCEPTION processing book {book_id}: {e}")
                failed_books += 1
                self.logger.error(f"{prefix} - ❌ Failed to process book {book_id}: {e}")

        # Summary
        print(f"🔥🔥🔥 PROCESSING SUMMARY: Success={successful_books}, Failed={failed_books}")
        self.logger.info(f"{prefix} - ✅ Success: {successful_books}, ❌ Failed: {failed_books}")

        if failed_books > 0:
            print(f"🔥🔥🔥 RAISING EXCEPTION due to failed books")
            raise Exception(f"Failed to process data for {failed_books}/{len(books)} books")

        print(f"🔥🔥🔥 ABOUT TO TRIGGER CALLBACKS")
        print(f"🔥🔥🔥 Calling _trigger_equity_callbacks with:")
        print(f"🔥🔥🔥   - books: {books}")
        print(f"🔥🔥🔥   - equity_bars count: {len(equity_bars)}")
        print(f"🔥🔥🔥   - is_backfill: {is_backfill}")

        # Trigger callbacks
        self._trigger_equity_callbacks(books, equity_bars, exchange_group_manager, is_backfill)

        print(f"🔥🔥🔥 EXITING process_books_sequentially - COMPLETE")

    def _process_single_book(self, book_context, equity_bars: List[EquityBar], fx: Optional[List[FXRate]]):
        """Process market data for a single book"""
        print(f"🔥🔥🔥 ENTERING _process_single_book")
        print(f"🔥🔥🔥 book_context type: {type(book_context)}")
        print(f"🔥🔥🔥 equity_bars count: {len(equity_bars) if equity_bars else 0}")

        import source.orchestration.app_state.state_manager as app_state_module

        original_app_state = app_state_module.app_state
        print(f"🔥🔥🔥 Saved original app_state")

        try:
            # Set book's app_state as current
            app_state_module.app_state = book_context.app_state
            print(f"🔥🔥🔥 Set book app_state as current")

            # Handle timing for first book only (others share the same timing)
            if not app_state_module.app_state._received_first_market_data:
                print(f"🔥🔥🔥 First market data - marking received")
                minute_bar_timestamp = datetime.fromisoformat(equity_bars[0].timestamp)
                app_state_module.app_state.mark_first_market_data_received(minute_bar_timestamp)

            # Process the exchange state
            print(f"🔥🔥🔥 Processing FX rates")
            self.processing_steps.process_fx_rates(fx)

            print(f"🔥🔥🔥 Processing exchange update")
            self.processing_steps.process_exchange_update(equity_bars)

            # Post process the states
            print(f"🔥🔥🔥 Processing portfolio update")
            self.processing_steps.process_portfolio_update(equity_bars)

            print(f"🔥🔥🔥 Processing accounts update")
            self.processing_steps.process_accounts_update()

            print(f"🔥🔥🔥 Processing returns update")
            self.processing_steps.process_returns_update(datetime.fromisoformat(equity_bars[0].timestamp))

            print(f"🔥🔥🔥 Processing orders update")
            self.processing_steps.process_order_progress_update(datetime.fromisoformat(equity_bars[0].timestamp))

            # Advance market bin
            print(f"🔥🔥🔥 Advancing market bin")
            self.processing_steps.advance_market_bin()

            print(f"🔥🔥🔥 Saving previous states")
            self.processing_steps.save_previous_states()

            print(f"🔥🔥🔥 _process_single_book COMPLETE")

        finally:
            # Restore original app_state
            app_state_module.app_state = original_app_state
            print(f"🔥🔥🔥 Restored original app_state")

    def _trigger_equity_callbacks(self, books: List[str], equity_bars: List[EquityBar],
                                  exchange_group_manager, is_backfill: bool):
        """Trigger equity manager callbacks after processing all books"""
        print(f"🔥🔥🔥 ENTERING _trigger_equity_callbacks")
        self.logger.info(f"🔥🔥🔥 _trigger_equity_callbacks CALLED")

        if not books:
            print(f"🔥🔥🔥 NO bookS PROVIDED - RETURNING")
            self.logger.warning("⚠️ No books provided to trigger callbacks")
            return

        if not equity_bars:
            print(f"🔥🔥🔥 NO EQUITY BARS PROVIDED - RETURNING")
            self.logger.warning("⚠️ No equity bars provided to trigger callbacks")
            return

        try:
            # Get first book's equity manager (shared across all books)
            print(f"🔥🔥🔥 Getting book context for first book: {books[0]}")
            first_book_context = exchange_group_manager.book_contexts[books[0]]
            print(f"🔥🔥🔥 Got book context: {first_book_context}")

            print(f"🔥🔥🔥 Getting equity manager from app_state")
            equity_manager = first_book_context.app_state.equity_manager
            print(f"🔥🔥🔥 Got equity manager: {equity_manager}")

            if equity_manager and hasattr(equity_manager, '_prepare_snapshot_data'):
                print(f"🔥🔥🔥 Equity manager HAS _prepare_snapshot_data method")

                # Check callback count
                callback_count = len(equity_manager._callbacks) if hasattr(equity_manager, '_callbacks') else 0
                print(f"🔥🔥🔥 Registered callbacks count: {callback_count}")

                if callback_count == 0:
                    print(f"🔥🔥🔥 WARNING: NO CALLBACKS REGISTERED - Session service not connected?")
                    self.logger.warning("⚠️ No callbacks registered - session service likely not connected")
                    return

                mode = "REPLAY/BACKFILL" if is_backfill else "LIVE"
                self.logger.info(f"🔥 Triggering equity callbacks for {mode} data")

                print(f"🔥🔥🔥 Preparing snapshot data...")
                snapshot_data = equity_manager._prepare_snapshot_data(equity_bars)
                print(f"🔥🔥🔥 Prepared {len(snapshot_data)} snapshot records")

                print(f"🔥🔥🔥 Calling _notify_callbacks...")
                equity_manager._notify_callbacks(snapshot_data)
                print(f"🔥🔥🔥 SUCCESS: Callbacks triggered!")

                self.logger.info(f"✅ Equity callbacks triggered successfully for {mode} data")
            else:
                print(f"🔥🔥🔥 ERROR: Equity manager missing _prepare_snapshot_data method!")
                print(f"🔥🔥🔥 equity_manager = {equity_manager}")
                print(
                    f"🔥🔥🔥 has _prepare_snapshot_data = {hasattr(equity_manager, '_prepare_snapshot_data') if equity_manager else False}")
                self.logger.warning("⚠️ No equity manager found or missing callback methods")

        except Exception as e:
            print(f"🔥🔥🔥 EXCEPTION in _trigger_equity_callbacks: {e}")
            self.logger.error(f"❌ Error triggering equity callbacks: {e}")
            print(f"🔥🔥🔥 Full traceback:")
            print(traceback.format_exc())
            self.logger.error(f"Full traceback: {traceback.format_exc()}")

        print(f"🔥🔥🔥 EXITING _trigger_equity_callbacks")