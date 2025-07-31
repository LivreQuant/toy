# source/orchestration/app_state/component_managers.py
import logging
from threading import RLock
from typing import Optional

from source.config import app_config
from source.simulation.core.interfaces.exchange import Exchange_ABC
from source.simulation.core.modules.dependency_injection import ExchangeSimulatorModule

# Import all manager classes
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
    """Configuration settings for exchange operations"""

    def __init__(self):
        self.MAX_DATA_WAIT_MINUTES = 60
        self.DATA_CHECK_INTERVAL_SECONDS = 5

        # Required data types that must be present
        self.REQUIRED_GLOBAL_DATA_TYPES = ["equity", "fx"]
        self.REQUIRED_USER_DATA_TYPES = ["portfolio", "accounts"]
        self.OPTIONAL_USER_DATA_TYPES = ["orders", "impact", "returns"]


class ComponentManagers:
    def __init__(self):
        self._lock = RLock()
        self.logger = logging.getLogger(self.__class__.__name__)

        # Core components
        self._exchange: Optional[Exchange_ABC] = None
        self._module: Optional[ExchangeSimulatorModule] = None

        # Configuration
        self.config = ExchangeConfig()

        # Initialize all managers with simple file tracking setting
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
                self._returns_manager is not None,
                self._cash_flow_manager is not None,
                self._risk_manager is not None,
                self._fx_manager is not None,
                self._trade_manager is not None,
                self._universe_manager is not None,
                self._impact_manager is not None,
                self._module is not None
            ])

    # Core component properties
    @property
    def exchange(self):
        with self._lock:
            return self._exchange

    @exchange.setter
    def exchange(self, value):
        with self._lock:
            self._exchange = value

    @property
    def module(self):
        with self._lock:
            return self._module

    @module.setter
    def module(self, value):
        with self._lock:
            self._module = value

    # Manager properties
    @property
    def conviction_manager(self):
        with self._lock:
            return self._conviction_manager

    @property
    def order_view_manager(self):
        with self._lock:
            return self._order_view_manager

    @property
    def portfolio_manager(self):
        with self._lock:
            return self._portfolio_manager

    @property
    def cash_flow_manager(self):
        with self._lock:
            return self._cash_flow_manager

    @property
    def universe_manager(self):
        with self._lock:
            return self._universe_manager

    @property
    def returns_manager(self):
        with self._lock:
            return self._returns_manager

    @property
    def account_manager(self):
        with self._lock:
            return self._account_manager

    @property
    def impact_manager(self):
        with self._lock:
            return self._impact_manager

    @property
    def equity_manager(self):
        with self._lock:
            return self._equity_manager

    @property
    def order_manager(self):
        with self._lock:
            return self._order_manager

    @property
    def trade_manager(self):
        with self._lock:
            return self._trade_manager

    @property
    def risk_manager(self):
        with self._lock:
            return self._risk_manager

    @property
    def fx_manager(self):
        with self._lock:
            return self._fx_manager

    def get_all_managers(self):
        """Get all manager instances"""
        with self._lock:
            return {
                'conviction': self._conviction_manager,
                'order_view': self._order_view_manager,
                'portfolio': self._portfolio_manager,
                'cash_flow': self._cash_flow_manager,
                'universe': self._universe_manager,
                'returns': self._returns_manager,
                'account': self._account_manager,
                'impact': self._impact_manager,
                'equity': self._equity_manager,
                'order': self._order_manager,
                'trade': self._trade_manager,
                'risk': self._risk_manager,
                'fx': self._fx_manager
            }

    def shutdown_all_managers(self):
        """Shutdown all managers properly"""
        with self._lock:
            managers = self.get_all_managers()
            for name, manager in managers.items():
                try:
                    if hasattr(manager, 'shutdown'):
                        manager.shutdown()
                        self.logger.info(f"✅ {name} manager shut down")
                except Exception as e:
                    self.logger.error(f"❌ Error shutting down {name} manager: {e}")

            # Shutdown the database writer
            from source.simulation.managers.utils import TrackingManager
            TrackingManager.shutdown_database_writer()
            self.logger.info("✅ Database writer shut down")