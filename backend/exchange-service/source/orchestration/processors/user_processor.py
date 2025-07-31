# source/orchestration/processors/user_processor.py
"""
User Processor - Handles processing data for all users
"""

import logging
from datetime import datetime
from typing import List, Optional

from source.simulation.managers.equity import EquityBar
from source.simulation.managers.fx import FXRate
from .processing_steps import ProcessingSteps


class UserProcessor:
    """Handles processing market data for all users"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.processing_steps = ProcessingSteps()

    def process_users_sequentially(self, users: List[str], equity_bars: List[EquityBar],
                                   fx: Optional[List[FXRate]], exchange_group_manager,
                                   is_backfill: bool = False) -> None:
        """Process market data for all users sequentially"""
        successful_users = 0
        failed_users = 0

        prefix = "🔄 BACKFILL" if is_backfill else "🔥 LIVE"
        self.logger.info(f"{prefix} - Processing {len(users)} users sequentially...")

        # Process each user
        for user_id in users:
            try:
                if user_id not in exchange_group_manager.user_contexts:
                    self.logger.error(f"❌ User {user_id} not found in user contexts")
                    failed_users += 1
                    continue

                user_context = exchange_group_manager.user_contexts[user_id]
                self.logger.info(f"{prefix} - Processing user {user_id}...")

                self._process_single_user(user_context, equity_bars, fx)
                successful_users += 1
                self.logger.info(f"{prefix} - ✅ User {user_id} processed successfully")

            except Exception as e:
                failed_users += 1
                self.logger.error(f"{prefix} - ❌ Failed to process user {user_id}: {e}")

        # Summary
        self.logger.info(f"{prefix} - ✅ Success: {successful_users}, ❌ Failed: {failed_users}")

        if failed_users > 0:
            raise Exception(f"Failed to process data for {failed_users}/{len(users)} users")

        # Trigger callbacks
        self._trigger_equity_callbacks(users, equity_bars, exchange_group_manager, is_backfill)

    def _process_single_user(self, user_context, equity_bars: List[EquityBar], fx: Optional[List[FXRate]]):
        """Process market data for a single user"""
        import source.orchestration.app_state.state_manager as app_state_module

        original_app_state = app_state_module.app_state

        try:
            # Set user's app_state as current
            app_state_module.app_state = user_context.app_state

            # Handle timing for first user only (others share the same timing)
            if not app_state_module.app_state._received_first_market_data:
                minute_bar_timestamp = datetime.fromisoformat(equity_bars[0].timestamp)
                app_state_module.app_state.mark_first_market_data_received(minute_bar_timestamp)

            # Process the exchange state
            self.processing_steps.process_fx_rates(fx)
            self.processing_steps.process_exchange_update(equity_bars)

            # Post process the states
            self.processing_steps.process_portfolio_update(equity_bars)
            self.processing_steps.process_accounts_update()
            self.processing_steps.process_returns_update(datetime.fromisoformat(equity_bars[0].timestamp))
            # IMPACT?

            # Advance market bin
            self.processing_steps.advance_market_bin()
            self.processing_steps.save_previous_states()

        finally:
            # Restore original app_state
            app_state_module.app_state = original_app_state

    def _trigger_equity_callbacks(self, users: List[str], equity_bars: List[EquityBar],
                                  exchange_group_manager, is_backfill: bool):
        """Trigger equity manager callbacks after processing all users"""
        if not users:
            return

        try:
            # Get first user's equity manager (shared across all users)
            first_user_context = exchange_group_manager.user_contexts[users[0]]
            equity_manager = first_user_context.app_state.equity_manager

            if equity_manager and hasattr(equity_manager, '_prepare_snapshot_data'):
                mode = "REPLAY/BACKFILL" if is_backfill else "LIVE"
                self.logger.info(f"🔥 Triggering equity callbacks for {mode} data")

                snapshot_data = equity_manager._prepare_snapshot_data(equity_bars)
                equity_manager._notify_callbacks(snapshot_data)

                self.logger.info(f"✅ Equity callbacks triggered successfully for {mode} data")
            else:
                self.logger.warning("⚠️ No equity manager found or missing callback methods")

        except Exception as e:
            self.logger.error(f"❌ Error triggering equity callbacks: {e}")
