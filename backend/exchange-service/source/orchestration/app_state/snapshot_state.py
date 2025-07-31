# source/orchestration/app_state/snapshot_state.py
"""
Snapshot State - Handles last snap data tracking
"""
import logging
from threading import RLock


class SnapshotState:
    def __init__(self):
        self._lock = RLock()
        self.logger = logging.getLogger(self.__class__.__name__)

        # Last Snap data flags
        self._has_universe = False
        self._has_last_snap_portfolio = False
        self._has_last_snap_account = False
        self._has_last_snap_impact = False
        self._has_last_snap_order = False
        self._has_last_snap_fx = False

        # Market data state - REMOVED from here, moved to MarketTiming
        self._market_data_pending = True

    def mark_universe_received(self):
        with self._lock:
            self._has_universe = True

    def mark_portfolio_received(self):
        with self._lock:
            self._has_last_snap_portfolio = True

    def mark_orders_received(self):
        with self._lock:
            self._has_last_snap_order = True

    def mark_impact_received(self):
        with self._lock:
            self._has_last_snap_impact = True

    def mark_account_received(self):
        with self._lock:
            self._has_last_snap_account = True

    def mark_fx_received(self):
        with self._lock:
            self._has_last_snap_fx = True

    def has_universe(self) -> bool:
        with self._lock:
            return self._has_universe

    def get_current_state(self) -> str:
        """Get detailed current state description"""
        with self._lock:
            if not self._has_universe:
                return "WAITING_FOR_UNIVERSE"

            if not self._has_last_snap_portfolio:
                return "WAITING_FOR_LAST_SNAP_PORTFOLIO"

            if not self._has_last_snap_order:
                return "WAITING_FOR_LAST_SNAP_ORDERS"

            if not self._has_last_snap_fx:
                return "WAITING_FOR_LAST_SNAP_FX"

            if not self._has_last_snap_impact:
                return "WAITING_FOR_LAST_SNAP_IMPACT"

            # NOTE: _received_first_market_data is now in MarketTiming
            # We'll need to check it there or pass it in
            if self._market_data_pending:
                return "WAITING_FOR_NEXT_MARKET_DATA"

            return "ACTIVE"

    def log_current_state(self):
        """Log current state with details"""
        with self._lock:
            state = self.get_current_state()

            if state == "WAITING_FOR_UNIVERSE":
                self.logger.info("Market data service connected - Waiting for universe definition")
            elif state == "WAITING_FOR_LAST_SNAP_PORTFOLIO":
                self.logger.info("Universe loaded - Waiting for last snapshot portfolio")
            elif state == "WAITING_FOR_NEXT_MARKET_DATA":
                self.logger.info("Processing complete - Waiting for next market data")
            elif state == "ACTIVE":
                self.logger.info("Market simulation active")

    def log_state_change(self, state: str):
        """Log state changes with appropriate messages"""
        if state == "INITIALIZING":
            self.logger.info("🔄 System initializing...")
        elif state == "WAITING_FOR_PORTFOLIO_DATA":
            self.logger.info("Portfolio loaded - Waiting for market data")
        elif state == "WAITING_FOR_NEXT_MARKET_DATA":
            self.logger.info("Processing complete - Waiting for next market data")
        elif state == "ACTIVE":
            self.logger.info("Market simulation active")
        elif state == "DEGRADED":
            self.logger.warning("Market simulation degraded - Check service status")

    def get_status_summary(self):
        """Get snapshot status summary"""
        with self._lock:
            return {
                "universe": self._has_universe,
                "portfolio": self._has_last_snap_portfolio,
                "account": self._has_last_snap_account,
                "impact": self._has_last_snap_impact,
                "order": self._has_last_snap_order,
                "fx": self._has_last_snap_fx,
                "market_data_pending": self._market_data_pending
            }