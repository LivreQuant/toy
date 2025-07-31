# source/orchestration/processors/processing_steps.py
"""
Processing Steps - Handles individual processing steps for market data
"""

import logging
import time
from datetime import datetime
from typing import List, Optional
from decimal import Decimal

from source.simulation.managers.equity import EquityBar
from source.simulation.managers.fx import FXRate


class ProcessingSteps:
    """Handles individual processing steps for market data processing"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def process_fx_rates(self, fx: Optional[List[FXRate]]) -> None:
        """Process FX rates"""
        from source.orchestration.app_state.state_manager import app_state

        step_start = time.time()
        if fx and app_state.fx_manager:
            self.logger.info("💱 STEP 1: FX RATES UPDATE")
            self.logger.info(f"   Updating {len(fx)} FX rates")
            app_state.fx_manager.update_rates(fx)
            step_duration = (time.time() - step_start) * 1000
            self.logger.info(f"✅ STEP 1 COMPLETE: FX rates updated in {step_duration:.2f}ms")
        else:
            self.logger.info("⏭️ STEP 1 SKIPPED: No FX rates to update")

    def process_exchange_update(self, equity_bars: List[EquityBar]) -> None:
        """Update exchange with equity data"""
        from source.orchestration.app_state.state_manager import app_state

        step_start = time.time()
        if app_state.exchange:
            self.logger.info("🏛️ STEP 2: EXCHANGE MARKET DATA UPDATE")

            for i, bar in enumerate(equity_bars):
                self.logger.debug(f"     [{i + 1}/{len(equity_bars)}] Processing {bar.symbol}")

                market_data = {
                    "symbol": bar.symbol,
                    "timestamp": bar.timestamp,
                    "currency": bar.currency,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "vwap": bar.vwap,
                    "vwas": bar.vwas,
                    "vwav": bar.vwav,
                    "price": bar.vwap,
                    "volume": bar.volume,
                    "count": bar.count
                }

                app_state.exchange.update_market_data(market_data)

            step_duration = (time.time() - step_start) * 1000
            self.logger.info(f"✅ STEP 2 COMPLETE: Exchange updated in {step_duration:.2f}ms")
        else:
            self.logger.error("❌ STEP 2 FAILED: No exchange available")
            raise ValueError("Exchange not available for market data update")

    def process_risk_update(self, risk_holdings, timestamp: datetime) -> None:
        """Update risk data"""
        from source.orchestration.app_state.state_manager import app_state

        step_start = time.time()
        if app_state.risk_manager and risk_holdings:
            self.logger.info("📊 STEP 2.5: RISK DATA UPDATE")
            app_state.risk_manager.update_from_risk_holdings(risk_holdings, timestamp)
            step_duration = (time.time() - step_start) * 1000
            self.logger.info(f"✅ STEP 2.5 COMPLETE: Risk data updated in {step_duration:.2f}ms")
        else:
            self.logger.warning("⚠️ STEP 2.5 SKIPPED: Risk manager not available or no risk holdings data")

    def process_portfolio_update(self, equity_bars: List[EquityBar]) -> None:
        """Update portfolio with new market prices"""
        from source.orchestration.app_state.state_manager import app_state

        step_start = time.time()
        if app_state.portfolio_manager:
            self.logger.info("💼 STEP 3: PORTFOLIO UPDATE")

            price_updates = {
                bar.symbol: Decimal(str(bar.close)) if isinstance(bar.close, float) else bar.close
                for bar in equity_bars
            }

            app_state.portfolio_manager.update_portfolio(price_updates)

            step_duration = (time.time() - step_start) * 1000
            self.logger.info(f"✅ STEP 3 COMPLETE: Portfolio updated in {step_duration:.2f}ms")
        else:
            self.logger.error("❌ STEP 3 FAILED: No portfolio manager available")

    def process_accounts_update(self) -> None:
        """Update account NAV and balances"""
        from source.orchestration.app_state.state_manager import app_state

        step_start = time.time()
        if app_state.account_manager:
            self.logger.info("🏦 STEP 4: ACCOUNT BALANCES UPDATE")
            app_state.account_manager.write_balances()
            step_duration = (time.time() - step_start) * 1000
            self.logger.info(f"✅ STEP 4 COMPLETE: Account balances updated in {step_duration:.2f}ms")
        else:
            self.logger.error("❌ STEP 4 FAILED: No account manager available")

    def process_cash_flow_update(self, timestamp: datetime) -> None:
        """Save cash flow data"""
        from source.orchestration.app_state.state_manager import app_state

        step_start = time.time()
        if app_state.cash_flow_manager:
            self.logger.info("💰 STEP 4.5: CASH FLOW DATA SAVE")
            cash_flows = app_state.cash_flow_manager.get_current_flows()
            if cash_flows:
                for user_id, flows in cash_flows.items():
                    self.logger.info(f"   Saving {len(flows)} cash flow records for user {user_id}")
                    app_state.db_manager.insert_simulation_data(
                        table_name='cash_flow_data',
                        data=flows,
                        user_id=user_id,
                        timestamp=timestamp
                    )
            else:
                self.logger.info("   No cash flow data to save.")
            step_duration = (time.time() - step_start) * 1000
            self.logger.info(f"✅ STEP 4.5 COMPLETE: Cash flow data saved in {step_duration:.2f}ms")
        else:
            self.logger.warning("⚠️ STEP 4.5 SKIPPED: Cash flow manager not available")

    def process_order_views_update(self, timestamp: datetime) -> None:
        """Update order views"""
        from source.orchestration.app_state.state_manager import app_state

        step_start = time.time()
        if app_state.order_manager and app_state.order_view_manager:
            self.logger.info("📋 STEP 5: ORDER VIEWS UPDATE")
            app_state.order_view_manager.update_orders_view(timestamp=timestamp)
            step_duration = (time.time() - step_start) * 1000
            self.logger.info(f"✅ STEP 5 COMPLETE: Order views updated in {step_duration:.2f}ms")
        else:
            self.logger.warning("⚠️ STEP 5 SKIPPED: Order manager or order view manager not available")

    def process_returns_update(self, timestamp: datetime) -> None:
        """Calculate returns"""
        from source.orchestration.app_state.state_manager import app_state

        step_start = time.time()
        if app_state.returns_manager:
            self.logger.info("📈 STEP 6: RETURNS COMPUTATION")
            app_state.returns_manager.compute_all_returns(timestamp=timestamp)
            step_duration = (time.time() - step_start) * 1000
            self.logger.info(f"✅ STEP 6 COMPLETE: Returns computed in {step_duration:.2f}ms")
        else:
            self.logger.warning("⚠️ STEP 6 SKIPPED: Returns manager not available")

    def advance_market_bin(self) -> None:
        """Advance to next market bin"""
        from source.orchestration.app_state.state_manager import app_state
        import traceback
        import threading

        step_start = time.time()

        # ✅ ADD DETAILED LOGGING
        self.logger.info("🚨 ADVANCE_MARKET_BIN CALLED! 🚨")
        self.logger.info(f"🧵 Thread: {threading.current_thread().name}")
        self.logger.info(f"🔍 Call stack:")

        # Log the call stack to see who called this
        stack = traceback.extract_stack()
        for i, frame in enumerate(stack[-5:-1]):  # Show last 4 frames
            self.logger.info(f"   [{i}] {frame.filename}:{frame.lineno} in {frame.name}")
            self.logger.info(f"       {frame.line}")

        self.logger.info("⏰ STEP 7: BIN ADVANCEMENT")

        old_current_bin = app_state.get_current_bin()
        old_next_bin = app_state.get_next_bin()
        old_current_timestamp = app_state.get_current_timestamp()
        old_next_timestamp = app_state.get_next_timestamp()

        self.logger.info(f"📊 BEFORE advance_bin():")
        self.logger.info(f"   Current Bin: {old_current_bin}")
        self.logger.info(f"   Next Bin: {old_next_bin}")
        self.logger.info(f"   Current Time: {old_current_timestamp}")
        self.logger.info(f"   Next Time: {old_next_timestamp}")

        app_state.advance_bin()

        new_current_bin = app_state.get_current_bin()
        new_next_bin = app_state.get_next_bin()
        new_current_timestamp = app_state.get_current_timestamp()
        new_next_timestamp = app_state.get_next_timestamp()

        self.logger.info(f"📊 AFTER advance_bin():")
        self.logger.info(f"   Current Bin: {new_current_bin}")
        self.logger.info(f"   Next Bin: {new_next_bin}")
        self.logger.info(f"   Current Time: {new_current_timestamp}")
        self.logger.info(f"   Next Time: {new_next_timestamp}")

        self.logger.info(f"   Advancement: {old_current_bin} → {new_current_bin}")
        self.logger.info(f"   Next: {old_next_bin} → {new_next_bin}")

        step_duration = (time.time() - step_start) * 1000
        self.logger.info(f"✅ STEP 7 COMPLETE: Bin advanced in {step_duration:.2f}ms")
        self.logger.info("🚨 ADVANCE_MARKET_BIN COMPLETE! 🚨")

    def save_previous_states(self) -> None:
        """Save current state as previous for next iteration"""
        from source.orchestration.app_state.state_manager import app_state

        step_start = time.time()
        self.logger.info("💾 STEP 8: STATE PRESERVATION")

        saved_managers = []
        if app_state.fx_manager:
            app_state.fx_manager.save_current_as_previous()
            saved_managers.append("FX")
        if app_state.account_manager:
            app_state.account_manager.save_current_as_previous()
            saved_managers.append("Account")
        if app_state.portfolio_manager:
            app_state.portfolio_manager.save_current_as_previous()
            saved_managers.append("Portfolio")
        if app_state.cash_flow_manager:
            app_state.cash_flow_manager.clear_current_flows()
            saved_managers.append("CashFlow")

        self.logger.info(f"   SAVED_STATES: {', '.join(saved_managers)}")

        step_duration = (time.time() - step_start) * 1000
        self.logger.info(f"✅ STEP 8 COMPLETE: State preserved in {step_duration:.2f}ms")
