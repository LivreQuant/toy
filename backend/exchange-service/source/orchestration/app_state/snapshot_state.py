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
        self._has_last_snap_equity = False
        self._has_last_snap_returns = False
        self._has_last_snap_risk = False
        self._has_last_snap_trades = False
        self._has_last_snap_conviction = False
        self._has_last_snap_cash_flow = False

        # Market data state - REMOVED from here, moved to MarketTiming
        self._market_data_pending = True

    def mark_universe_received(self):
        with self._lock:
            self._has_universe = True
            self.logger.debug("✅ Universe snapshot received")

    def mark_portfolio_received(self):
        with self._lock:
            self._has_last_snap_portfolio = True
            self.logger.debug("✅ Portfolio snapshot received")

    def mark_orders_received(self):
        with self._lock:
            self._has_last_snap_order = True
            self.logger.debug("✅ Orders snapshot received")

    def mark_impact_received(self):
        with self._lock:
            self._has_last_snap_impact = True
            self.logger.debug("✅ Impact snapshot received")

    def mark_account_received(self):
        with self._lock:
            self._has_last_snap_account = True
            self.logger.debug("✅ Account snapshot received")

    def mark_accounts_received(self):
        """Alias for mark_account_received - both singular and plural versions"""
        self.mark_account_received()

    def mark_fx_received(self):
        with self._lock:
            self._has_last_snap_fx = True
            self.logger.debug("✅ FX snapshot received")

    def mark_equity_received(self):
        with self._lock:
            self._has_last_snap_equity = True
            self.logger.debug("✅ Equity snapshot received")

    def mark_returns_received(self):
        with self._lock:
            self._has_last_snap_returns = True
            self.logger.debug("✅ Returns snapshot received")

    def mark_risk_received(self):
        with self._lock:
            self._has_last_snap_risk = True
            self.logger.debug("✅ Risk snapshot received")

    def mark_trades_received(self):
        with self._lock:
            self._has_last_snap_trades = True
            self.logger.debug("✅ Trades snapshot received")

    def mark_conviction_received(self):
        with self._lock:
            self._has_last_snap_conviction = True
            self.logger.debug("✅ Conviction snapshot received")

    def mark_cash_flow_received(self):
        with self._lock:
            self._has_last_snap_cash_flow = True
            self.logger.debug("✅ Cash flow snapshot received")

    def has_universe(self) -> bool:
        with self._lock:
            return self._has_universe

    def has_portfolio(self) -> bool:
        with self._lock:
            return self._has_last_snap_portfolio

    def has_accounts(self) -> bool:
        with self._lock:
            return self._has_last_snap_account

    def has_orders(self) -> bool:
        with self._lock:
            return self._has_last_snap_order

    def has_fx(self) -> bool:
        with self._lock:
            return self._has_last_snap_fx

    def has_impact(self) -> bool:
        with self._lock:
            return self._has_last_snap_impact

    def has_equity(self) -> bool:
        with self._lock:
            return self._has_last_snap_equity

    def has_returns(self) -> bool:
        with self._lock:
            return self._has_last_snap_returns

    def has_risk(self) -> bool:
        with self._lock:
            return self._has_last_snap_risk

    def has_trades(self) -> bool:
        with self._lock:
            return self._has_last_snap_trades

    def has_conviction(self) -> bool:
        with self._lock:
            return self._has_last_snap_conviction

    def has_cash_flow(self) -> bool:
        with self._lock:
            return self._has_last_snap_cash_flow

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

            if not self._has_last_snap_account:
                return "WAITING_FOR_LAST_SNAP_ACCOUNTS"

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
            elif state == "WAITING_FOR_LAST_SNAP_ORDERS":
                self.logger.info("Portfolio loaded - Waiting for last snapshot orders")
            elif state == "WAITING_FOR_LAST_SNAP_FX":
                self.logger.info("Orders loaded - Waiting for last snapshot FX rates")
            elif state == "WAITING_FOR_LAST_SNAP_ACCOUNTS":
                self.logger.info("FX rates loaded - Waiting for last snapshot accounts")
            elif state == "WAITING_FOR_LAST_SNAP_IMPACT":
                self.logger.info("Accounts loaded - Waiting for last snapshot impact")
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
                "equity": self._has_last_snap_equity,
                "returns": self._has_last_snap_returns,
                "risk": self._has_last_snap_risk,
                "trades": self._has_last_snap_trades,
                "conviction": self._has_last_snap_conviction,
                "cash_flow": self._has_last_snap_cash_flow,
                "market_data_pending": self._market_data_pending
            }

    def reset(self):
        """Reset all snapshot state flags"""
        with self._lock:
            self._has_universe = False
            self._has_last_snap_portfolio = False
            self._has_last_snap_account = False
            self._has_last_snap_impact = False
            self._has_last_snap_order = False
            self._has_last_snap_fx = False
            self._has_last_snap_equity = False
            self._has_last_snap_returns = False
            self._has_last_snap_risk = False
            self._has_last_snap_trades = False
            self._has_last_snap_conviction = False
            self._has_last_snap_cash_flow = False
            self._market_data_pending = True
            self.logger.info("🔄 Snapshot state reset")

    def is_ready_for_market_data(self) -> bool:
        """Check if all required snapshots are received and ready for market data"""
        with self._lock:
            required_snapshots = [
                self._has_universe,
                self._has_last_snap_portfolio,
                self._has_last_snap_account,
                self._has_last_snap_fx
            ]
            return all(required_snapshots)

    def set_market_data_pending(self, pending: bool):
        """Set market data pending status"""
        with self._lock:
            self._market_data_pending = pending
            if not pending:
                self.logger.info("📊 Market data processing completed")