# source/orchestration/servers/session/state_managers/composite_state_manager.py
"""
Updated Composite State Manager
Coordinates all individual state managers including the missing ones
"""

import logging
from source.api.grpc.session_exchange_interface_pb2 import ExchangeDataUpdate
from .trade_manager import TradeStateManager
from .order_manager import OrderStateManager
from .portfolio_manager import PortfolioStateManager
from .account_manager import AccountStateManager
from .fx_manager import FXStateManager
from .universe_manager import UniverseStateManager
from .risk_manager import RiskStateManager
from .returns_manager import ReturnsStateManager
from .impact_manager import ImpactStateManager


class CompositeStateManager:
    """Coordinates all state managers for session server"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

        # Initialize all state managers
        self.trade_manager = TradeStateManager()
        self.order_manager = OrderStateManager()
        self.portfolio_manager = PortfolioStateManager()
        self.account_manager = AccountStateManager()
        self.fx_manager = FXStateManager()
        self.universe_manager = UniverseStateManager()
        self.risk_manager = RiskStateManager()
        self.returns_manager = ReturnsStateManager()
        self.impact_manager = ImpactStateManager()

    def add_user_state(self, update: ExchangeDataUpdate, user_context):
        """Add state from a single user using all state managers"""
        # Temporarily set app_state to get data
        import source.orchestration.app_state.state_manager as app_state_module
        original_app_state = app_state_module.app_state

        try:
            app_state_module.app_state = user_context.app_state

            # Use all state managers to populate the update
            self.order_manager.add_current_orders_state(update)
            self.portfolio_manager.add_current_portfolio_state(update)
            self.account_manager.add_current_accounts_state(update)
            self.fx_manager.add_current_fx_state(update)
            self.trade_manager.add_current_trades_state(update)
            self.universe_manager.add_current_universe_state(update)
            self.risk_manager.add_current_risk_state(update)
            self.returns_manager.add_current_returns_state(update)
            self.impact_manager.add_current_impact_state(update)

        finally:
            app_state_module.app_state = original_app_state