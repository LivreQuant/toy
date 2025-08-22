# source/orchestration/persistence/managers/manager_initializer.py
import logging
from datetime import datetime
import traceback
from typing import Dict, List
from decimal import Decimal


class ManagerInitializer:
    """Handles initialization of all simulation managers"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def initialize_universe(self, universe_data: Dict) -> bool:
        """Initialize universe manager - EXACTLY AS ORIGINAL"""
        try:
            from source.orchestration.app_state.state_manager import app_state

            if not app_state.universe_manager:
                self.logger.error("❌ Universe manager not available")
                return False

            app_state.universe_manager.set_universe({
                'symbols': universe_data,
                'universe_id': 'SNAPSHOT_UNIVERSE',
                'description': 'Snapshot Universe'
            })

            app_state.mark_last_snap_universe_received()
            self.logger.info(f"✅ Universe initialized with {len(universe_data)} symbols")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error initializing universe: {e}")
            return False

    def initialize_fx(self, fx_data: List, date: datetime) -> bool:
        """Initialize FX manager - EXACTLY AS ORIGINAL"""
        try:
            from source.orchestration.app_state.state_manager import app_state

            if not app_state.fx_manager:
                self.logger.error("❌ FX manager not available")
                return False

            app_state.fx_manager.submit_last_snap_rates(fx_data, date)
            app_state.mark_last_snap_fx_received()
            self.logger.info(f"✅ FX rates initialized with {len(fx_data)} rates")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error initializing FX rates: {e}")
            return False

    def initialize_portfolio(self, portfolio_data: Dict, date: datetime) -> bool:
        """Initialize portfolio manager BEFORE accounts (accounts need portfolio for NAV) - EXACTLY AS ORIGINAL"""
        try:
            from source.orchestration.app_state.state_manager import app_state

            if not app_state.portfolio_manager:
                self.logger.error("❌ Portfolio manager not available")
                return False

            self.logger.info("💼 INITIALIZING PORTFOLIO FROM SNAPSHOT")
            self.logger.info(f"📊 Number of positions: {len(portfolio_data)}")

            # Debug: Check the structure and convert if needed
            if portfolio_data:
                first_key = list(portfolio_data.keys())[0]
                first_item = portfolio_data[first_key]

                # If it's a Position object, convert to dict format
                if hasattr(first_item, 'symbol'):
                    self.logger.info("🔧 Converting Position objects to dictionary format...")
                    converted_portfolio_data = {}

                    for symbol, position in portfolio_data.items():
                        converted_portfolio_data[symbol] = {
                            'symbol': position.symbol,
                            'quantity': float(position.quantity),
                            'target_quantity': float(position.target_quantity),
                            'currency': position.currency,
                            'avg_price': float(position.avg_price),
                            'mtm_value': float(position.mtm_value),
                            'sod_realized_pnl': float(position.sod_realized_pnl),
                            'itd_realized_pnl': float(position.itd_realized_pnl),
                            'realized_pnl': float(position.realized_pnl),
                            'unrealized_pnl': float(position.unrealized_pnl)
                        }

                    portfolio_data = converted_portfolio_data

            app_state.portfolio_manager.initialize_portfolio(portfolio_data, date)
            app_state.mark_last_snap_portfolio_received()

            # Verify positions were loaded
            loaded_positions = app_state.portfolio_manager.get_all_positions()
            self.logger.info(f"✅ Portfolio initialized with {len(loaded_positions)} positions")

            for symbol, position in loaded_positions.items():
                self.logger.debug(f"   ✓ {symbol}: qty={position.quantity}, mtm=${position.mtm_value}")

            return True

        except Exception as e:
            self.logger.error(f"❌ Error initializing portfolio: {e}")
            self.logger.error(f"   Full traceback: {traceback.format_exc()}")
            return False

    def initialize_accounts(self, account_data: Dict, date: datetime) -> bool:
        """Initialize account manager AFTER portfolio (depends on portfolio for NAV calculation) - EXACTLY AS ORIGINAL"""
        try:
            from source.orchestration.app_state.state_manager import app_state

            if not app_state.account_manager:
                self.logger.error("❌ Account manager not available")
                return False

            if not app_state.portfolio_manager:
                self.logger.error("❌ Portfolio manager must be initialized before account manager")
                return False

            app_state.account_manager.initialize_account(account_data, date)
            app_state.mark_last_snap_account_received()

            total_balances = sum(len(balances) for balances in account_data.values())
            self.logger.info(f"✅ Accounts initialized with {total_balances} balances + portfolio NAV")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error initializing accounts: {e}")
            return False

    def initialize_equity(self, equity_data: List, date: datetime) -> bool:
        """Initialize equity data manager - EXACTLY AS ORIGINAL"""
        try:
            from source.orchestration.app_state.state_manager import app_state

            if not app_state.equity_manager:
                self.logger.error("❌ Equity data manager not available")
                return False

            app_state.equity_manager.insert_last_snap_equity(equity_data, date)
            self.logger.info(f"✅ Equity data initialized with {len(equity_data)} symbols")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error initializing equity data: {e}")
            return False

    def initialize_impact(self, impact_data: Dict, date: datetime) -> bool:
        """Initialize impact manager - EXACTLY AS ORIGINAL"""
        try:
            from source.orchestration.app_state.state_manager import app_state

            if not app_state.impact_manager:
                self.logger.error("❌ Impact manager not available")
                return False

            app_state.impact_manager.initialize_impacts(impact_data, date)
            app_state.mark_last_snap_impact_received()
            self.logger.info(f"✅ Impact initialized with {len(impact_data)} states")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error initializing impact: {e}")
            return False

    def initialize_orders(self, order_data: Dict, date: datetime) -> bool:
        """Initialize order manager AND submit orders to markets - EXACTLY AS ORIGINAL"""
        try:
            from source.orchestration.app_state.state_manager import app_state

            if not app_state.order_manager:
                self.logger.error("❌ Order manager not available")
                return False

            # Load orders into OrderManager (no file writing)
            app_state.order_manager.initialize_orders(order_data, date)
            app_state.mark_last_snap_orders_received()

            # Submit orders to the actual markets (skip OrderManager to avoid file writing)
            if app_state.exchange:
                for order_id, order_info in order_data.items():
                    try:
                        symbol = order_info['symbol']
                        market = app_state.exchange.get_market(symbol)

                        # Convert side string to enum
                        from source.simulation.core.enums.side import Side
                        side = Side.Buy if order_info['side'].upper() == 'BUY' else Side.Sell

                        # Submit order to market
                        submit_timestamp = order_info['submit_timestamp']
                        if isinstance(submit_timestamp, str):
                            submit_timestamp = datetime.fromisoformat(submit_timestamp.replace('Z', '+00:00'))

                        market.add_order(
                            submit_timestamp=submit_timestamp,
                            side=side,
                            qty=int(order_info['original_qty']),
                            currency=order_info['currency'],
                            price=Decimal(str(order_info['price'])) if order_info['price'] > 0 else None,
                            cl_order_id=order_info['cl_order_id'],
                            order_type=order_info['order_type'],
                            participation_rate=float(order_info['participation_rate']),
                            order_id=order_id,
                            skip_order_manager=True
                        )

                        self.logger.debug(f"✅ Submitted snapshot order {order_id} to {symbol} market")

                    except Exception as e:
                        self.logger.error(f"❌ Failed to submit snapshot order {order_id}: {e}")
                        return False

            self.logger.info(f"✅ Orders initialized with {len(order_data)} orders")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error initializing orders: {e}")
            return False

    def initialize_returns(self, returns_data: Dict, date: datetime) -> bool:
        """Initialize returns manager with period baseline data - EXACTLY AS ORIGINAL"""
        try:
            from source.orchestration.app_state.state_manager import app_state

            if not app_state.returns_manager:
                self.logger.error("❌ Returns manager not available")
                return False

            if returns_data and 'period_starts' in returns_data:
                period_starts = returns_data['period_starts']
                if isinstance(period_starts, list):
                    self.logger.info(f"🔍 Found {len(period_starts)} period baseline entries")
                    app_state.returns_manager.initialize_period_baselines(returns_data, date)
                    self.logger.info(f"✅ Returns period baselines initialized with {len(period_starts)} entries")
                else:
                    self.logger.warning(f"⚠️ period_starts is not a list: {type(period_starts)}")
            else:
                self.logger.info("✅ Returns initialized with no period baselines (empty data)")

            return True

        except Exception as e:
            self.logger.error(f"❌ Error initializing returns: {e}")
            self.logger.error(f"   Full traceback: {traceback.format_exc()}")
            return False

    def get_initialization_steps(self) -> List[tuple]:
        """Get the standard initialization steps in correct order"""
        return [
            ("FX rates", self.initialize_fx),
            ("Portfolio", self.initialize_portfolio),
            ("Accounts", self.initialize_accounts),
            ("Equity data", self.initialize_equity),
            ("Impact states", self.initialize_impact),
            ("Orders", self.initialize_orders),
            ("Returns", self.initialize_returns)
        ]