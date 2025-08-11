# source/orchestration/app_state/component_managers.py
import logging
from threading import RLock
from typing import Optional

from source.simulation.core.interfaces.exchange import Exchange_ABC
from source.simulation.core.modules.dependency_injection import ExchangeSimulatorModule
from source.simulation.managers.conviction import ConvictionManager
from source.simulation.managers.order_view import OrderViewManager
from source.simulation.managers.portfolio import PortfolioManager
from source.simulation.managers.cash_flow import CashFlowManager
from source.simulation.managers.universe import UniverseManager
from source.simulation.managers.returns import ReturnsManager
from source.simulation.managers.account import AccountManager
from source.simulation.managers.impact import ImpactManager
from source.simulation.managers.equity import EquityManager
from source.simulation.managers.order import OrderManager
from source.simulation.managers.trade import TradeManager
from source.simulation.managers.risk import RiskManager
from source.simulation.managers.fx import FXManager


class ExchangeConfig:
    """Configuration for exchange operations"""
    MAX_DATA_WAIT_MINUTES = 60
    DATA_CHECK_INTERVAL_SECONDS = 5
    REQUIRED_GLOBAL_DATA_TYPES = ["equity", "fx"]
    REQUIRED_USER_DATA_TYPES = ["portfolio", "accounts"]
    OPTIONAL_USER_DATA_TYPES = ["orders", "impact", "returns"]


class ComponentManagers:
    """Manages component instances and business logic managers"""

    def __init__(self):
        self._lock = RLock()
        self.logger = logging.getLogger(self.__class__.__name__)

        # Core components
        self._exchange: Optional[Exchange_ABC] = None
        self._module: Optional[ExchangeSimulatorModule] = None

        # Config
        self.config = ExchangeConfig()

        # Initialize all managers with simple file tracking setting
        from source.config import app_config

        self._conviction_manager = ConvictionManager(tracking=False)  # Market data - never tracked
        self._order_view_manager = OrderViewManager(tracking=True)
        self._portfolio_manager = PortfolioManager(tracking=True)
        self._cash_flow_manager = CashFlowManager(tracking=True)
        self._universe_manager = UniverseManager(tracking=False)  # Market data - never tracked
        self._returns_manager = ReturnsManager(tracking=True)
        self._account_manager = AccountManager(tracking=True)
        self._impact_manager = ImpactManager(tracking=True)
        self._equity_manager = EquityManager(tracking=False)  # Market data - never tracked
        self._order_manager = OrderManager(tracking=True)
        self._trade_manager = TradeManager(tracking=True)
        self._risk_manager = RiskManager(tracking=True)
        self._fx_manager = FXManager(tracking=False)  # Market data - never tracked

        storage_type = "DATABASE" if app_config.use_database_storage else "FILES"
        self.logger.info(f"✅ All managers initialized - Storage: {storage_type}")

        # Log the critical production mode check
        if app_config.is_production:
            self.logger.info("🚫 PRODUCTION MODE: File tracking DISABLED - using database storage only")
        else:
            self.logger.info(f"🔧 DEVELOPMENT MODE: File tracking ENABLED - using file storage only")

    def set_user_context(self, user_id: str) -> None:
        """Set user context for all managers that need it"""
        with self._lock:
            if self._order_manager:
                self._order_manager.set_user_context(user_id)
                self.logger.debug(f"📋 Set user context {user_id} in OrderManager")

            if self._trade_manager and hasattr(self._trade_manager, 'set_user_context'):
                self._trade_manager.set_user_context(user_id)
                self.logger.debug(f"📋 Set user context {user_id} in TradeManager")

            if self._portfolio_manager and hasattr(self._portfolio_manager, 'set_user_context'):
                self._portfolio_manager.set_user_context(user_id)
                self.logger.debug(f"📋 Set user context {user_id} in PortfolioManager")

            if self._account_manager and hasattr(self._account_manager, 'set_user_context'):
                self._account_manager.set_user_context(user_id)
                self.logger.debug(f"📋 Set user context {user_id} in AccountManager")

            if self._cash_flow_manager and hasattr(self._cash_flow_manager, 'set_user_context'):
                self._cash_flow_manager.set_user_context(user_id)
                self.logger.debug(f"📋 Set user context {user_id} in CashFlowManager")

            if self._returns_manager and hasattr(self._returns_manager, 'set_user_context'):
                self._returns_manager.set_user_context(user_id)
                self.logger.debug(f"📋 Set user context {user_id} in ReturnsManager")

            if self._impact_manager and hasattr(self._impact_manager, 'set_user_context'):
                self._impact_manager.set_user_context(user_id)
                self.logger.debug(f"📋 Set user context {user_id} in ImpactManager")

            if self._risk_manager and hasattr(self._risk_manager, 'set_user_context'):
                self._risk_manager.set_user_context(user_id)
                self.logger.debug(f"📋 Set user context {user_id} in RiskManager")

            if self._order_view_manager and hasattr(self._order_view_manager, 'set_user_context'):
                self._order_view_manager.set_user_context(user_id)
                self.logger.debug(f"📋 Set user context {user_id} in OrderViewManager")

    def is_initialized(self) -> bool:
        with self._lock:
            return all([
                self._exchange is not None,
                self._account_manager is not None,
                self._equity_manager is not None,
                self._order_view_manager is not None,
                self._order_manager is not None,
                self._conviction_manager is not None,
                self._portfolio_manager is not None,
                self._cash_flow_manager is not None,
                self._universe_manager is not None,
                self._returns_manager is not None,
                self._impact_manager is not None,
                self._trade_manager is not None,
                self._risk_manager is not None,
                self._fx_manager is not None
            ])

    def shutdown_all_managers(self) -> None:
        """Shutdown all managers and clean up resources"""
        with self._lock:
            managers = [
                self._conviction_manager,
                self._order_view_manager,
                self._portfolio_manager,
                self._cash_flow_manager,
                self._universe_manager,
                self._returns_manager,
                self._account_manager,
                self._impact_manager,
                self._equity_manager,
                self._order_manager,
                self._trade_manager,
                self._risk_manager,
                self._fx_manager
            ]

            for manager in managers:
                if manager and hasattr(manager, 'shutdown'):
                    try:
                        manager.shutdown()
                    except Exception as e:
                        self.logger.error(f"Error shutting down manager {type(manager).__name__}: {e}")

            self.logger.info("🔄 All managers shutdown completed")

    # Core components
    @property
    def exchange(self) -> Optional[Exchange_ABC]:
        with self._lock:
            return self._exchange

    @exchange.setter
    def exchange(self, value: Exchange_ABC):
        with self._lock:
            self._exchange = value

    @property
    def module(self) -> Optional[ExchangeSimulatorModule]:
        with self._lock:
            return self._module

    @module.setter
    def module(self, value: ExchangeSimulatorModule):
        with self._lock:
            self._module = value

    # Business logic managers
    @property
    def conviction_manager(self) -> ConvictionManager:
        with self._lock:
            return self._conviction_manager

    @property
    def order_view_manager(self) -> OrderViewManager:
        with self._lock:
            return self._order_view_manager

    @property
    def portfolio_manager(self) -> PortfolioManager:
        with self._lock:
            return self._portfolio_manager

    @property
    def cash_flow_manager(self) -> CashFlowManager:
        with self._lock:
            return self._cash_flow_manager

    @property
    def universe_manager(self) -> UniverseManager:
        with self._lock:
            return self._universe_manager

    @property
    def returns_manager(self) -> ReturnsManager:
        with self._lock:
            return self._returns_manager

    @property
    def account_manager(self) -> AccountManager:
        with self._lock:
            return self._account_manager

    @property
    def impact_manager(self) -> ImpactManager:
        with self._lock:
            return self._impact_manager

    @property
    def equity_manager(self) -> EquityManager:
        with self._lock:
            return self._equity_manager

    @property
    def order_manager(self) -> OrderManager:
        with self._lock:
            return self._order_manager

    @property
    def trade_manager(self) -> TradeManager:
        with self._lock:
            return self._trade_manager

    @property
    def risk_manager(self) -> RiskManager:
        with self._lock:
            return self._risk_manager

    @property
    def fx_manager(self) -> FXManager:
        with self._lock:
            return self._fx_manager

    def get_manager_by_name(self, manager_name: str):
        """Get a manager by its name"""
        with self._lock:
            manager_map = {
                'conviction_manager': self._conviction_manager,
                'order_view_manager': self._order_view_manager,
                'portfolio_manager': self._portfolio_manager,
                'cash_flow_manager': self._cash_flow_manager,
                'universe_manager': self._universe_manager,
                'returns_manager': self._returns_manager,
                'account_manager': self._account_manager,
                'impact_manager': self._impact_manager,
                'equity_manager': self._equity_manager,
                'order_manager': self._order_manager,
                'trade_manager': self._trade_manager,
                'risk_manager': self._risk_manager,
                'fx_manager': self._fx_manager
            }
            return manager_map.get(manager_name)

    def get_all_managers(self) -> dict:
        """Get all managers as a dictionary"""
        with self._lock:
            return {
                'conviction_manager': self._conviction_manager,
                'order_view_manager': self._order_view_manager,
                'portfolio_manager': self._portfolio_manager,
                'cash_flow_manager': self._cash_flow_manager,
                'universe_manager': self._universe_manager,
                'returns_manager': self._returns_manager,
                'account_manager': self._account_manager,
                'impact_manager': self._impact_manager,
                'equity_manager': self._equity_manager,
                'order_manager': self._order_manager,
                'trade_manager': self._trade_manager,
                'risk_manager': self._risk_manager,
                'fx_manager': self._fx_manager
            }

    def get_manager_status(self) -> dict:
        """Get status of all managers"""
        with self._lock:
            status = {}
            managers = self.get_all_managers()

            for name, manager in managers.items():
                if manager:
                    status[name] = {
                        'initialized': True,
                        'type': type(manager).__name__,
                        'tracking': getattr(manager, 'tracking', False) if hasattr(manager, 'tracking') else None
                    }

                    # Add specific status information if available
                    if hasattr(manager, 'get_status'):
                        status[name]['status'] = manager.get_status()
                    elif hasattr(manager, 'get_statistics'):
                        status[name]['statistics'] = manager.get_statistics()
                else:
                    status[name] = {'initialized': False}

            return status

    def reset_all_managers(self) -> None:
        """Reset all managers to initial state"""
        with self._lock:
            managers = self.get_all_managers()

            for name, manager in managers.items():
                if manager and hasattr(manager, 'reset'):
                    try:
                        manager.reset()
                        self.logger.info(f"✅ Reset {name}")
                    except Exception as e:
                        self.logger.error(f"❌ Error resetting {name}: {e}")
                elif manager and hasattr(manager, 'clear_all_data'):
                    try:
                        manager.clear_all_data()
                        self.logger.info(f"✅ Cleared data for {name}")
                    except Exception as e:
                        self.logger.error(f"❌ Error clearing data for {name}: {e}")

            self.logger.info("🔄 All managers reset completed")

    def validate_managers(self) -> dict:
        """Validate all managers and return validation results"""
        with self._lock:
            validation_results = {}
            managers = self.get_all_managers()

            for name, manager in managers.items():
                try:
                    if manager:
                        # Basic validation
                        validation_results[name] = {
                            'exists': True,
                            'type': type(manager).__name__,
                            'has_required_methods': True
                        }

                        # Check for required methods
                        required_methods = ['__init__']
                        missing_methods = [method for method in required_methods if not hasattr(manager, method)]

                        if missing_methods:
                            validation_results[name]['has_required_methods'] = False
                            validation_results[name]['missing_methods'] = missing_methods

                        # Run custom validation if available
                        if hasattr(manager, 'validate'):
                            validation_results[name]['custom_validation'] = manager.validate()
                    else:
                        validation_results[name] = {
                            'exists': False,
                            'error': 'Manager is None'
                        }

                except Exception as e:
                    validation_results[name] = {
                        'exists': bool(manager),
                        'error': str(e)
                    }

            return validation_results