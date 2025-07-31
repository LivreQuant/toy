# source/orchestration/app_state/state_manager.py
"""
Main State Manager - Coordination only
"""
import logging
from threading import RLock
from typing import Optional

from .snapshot_state import SnapshotState
from .market_timing import MarketTiming
from .service_health import ServiceHealth
from .component_managers import ComponentManagers

logger = logging.getLogger(__name__)


class AppState:
    def __init__(self):
        self._lock = RLock()
        self.logger = logging.getLogger(self.__class__.__name__)

        # Delegate to focused modules
        self.snapshot_state = SnapshotState()
        self.market_timing = MarketTiming()
        self.service_health = ServiceHealth()
        self.components = ComponentManagers()

        # User context only
        self._user_id: Optional[str] = None
        self._base_currency = 'USD'

    def get_app_state(self) -> str:
        """Get current application state"""
        with self._lock:
            if not self.components.is_initialized():
                return "INITIALIZING"
            if not self.service_health.is_healthy():
                return "DEGRADED"
            return "ACTIVE"

    def get_current_state(self) -> str:
        """Get detailed current state"""
        with self._lock:
            if not self.components.is_initialized():
                return "INITIALIZING"
            return self.snapshot_state.get_current_state()

    def is_initialized(self) -> bool:
        return self.components.is_initialized()

    def is_healthy(self) -> bool:
        return self.service_health.is_healthy()

    def request_shutdown(self) -> None:
        self.service_health.shutdown_all_services()

    # Snapshot state delegation
    def mark_last_snap_universe_received(self):
        self.snapshot_state.mark_universe_received()

    def mark_last_snap_portfolio_received(self):
        self.snapshot_state.mark_portfolio_received()

    def mark_last_snap_orders_received(self):
        self.snapshot_state.mark_orders_received()

    def mark_last_snap_impact_received(self):
        self.snapshot_state.mark_impact_received()

    def mark_last_snap_account_received(self):
        self.snapshot_state.mark_account_received()

    def mark_last_snap_fx_received(self):
        self.snapshot_state.mark_fx_received()

    def has_universe(self) -> bool:
        return self.snapshot_state.has_universe()

    def log_current_state(self):
        self.snapshot_state.log_current_state()

    # Market timing delegation
    def get_current_bin(self):
        return self.market_timing.get_current_bin()

    def get_next_bin(self):
        return self.market_timing.get_next_bin()

    def get_current_timestamp(self):
        return self.market_timing.get_current_timestamp()

    def get_next_timestamp(self):
        return self.market_timing.get_next_timestamp()

    def advance_bin(self):
        self.market_timing.advance_bin()

    def mark_first_market_data_received(self, timestamp):
        self.market_timing.mark_first_market_data_received(timestamp)

    def initialize_bin(self, timestamp):
        self.market_timing.initialize_bin(timestamp)

    def set_base_date(self, date):
        self.market_timing.set_base_date(date)

    def is_market_open(self, check_time=None):
        return self.market_timing.is_market_open(check_time)

    # ADD THIS - the processor needs this attribute directly
    @property
    def _received_first_market_data(self):
        return self.market_timing._received_first_market_data

    @_received_first_market_data.setter
    def _received_first_market_data(self, value):
        self.market_timing._received_first_market_data = value

    # Service health delegation
    def mark_service_started(self, service_name: str):
        self.service_health.mark_service_started(service_name)

    def mark_service_stopped(self, service_name: str):
        self.service_health.mark_service_stopped(service_name)

    def record_initialization_error(self, service_name: str, error: str):
        self.service_health.record_initialization_error(service_name, error)

    def get_service_status(self, service_name: str):
        return self.service_health.get_service_status(service_name)

    def get_health_status(self):
        return self.service_health.get_health_status()

    def set_market_data_service_available(self, available: bool):
        self.service_health.set_market_data_service_available(available)

    def is_market_data_service_available(self) -> bool:
        return self.service_health.is_market_data_service_available()

    def set_market_data_health_checker(self, checker):
        self.service_health.set_market_data_health_checker(checker)

    # Manager properties - delegate to components
    @property
    def exchange(self):
        return self.components.exchange

    @exchange.setter
    def exchange(self, value):
        self.components.exchange = value

    @property
    def module(self):
        return self.components.module

    @module.setter
    def module(self, value):
        self.components.module = value

    @property
    def conviction_manager(self):
        return self.components.conviction_manager

    @property
    def order_view_manager(self):
        return self.components.order_view_manager

    @property
    def portfolio_manager(self):
        return self.components.portfolio_manager

    @property
    def cash_flow_manager(self):
        return self.components.cash_flow_manager

    @property
    def universe_manager(self):
        return self.components.universe_manager

    @property
    def returns_manager(self):
        return self.components.returns_manager

    @property
    def account_manager(self):
        return self.components.account_manager

    @property
    def impact_manager(self):
        return self.components.impact_manager

    @property
    def equity_manager(self):
        return self.components.equity_manager

    @property
    def order_manager(self):
        return self.components.order_manager

    @property
    def trade_manager(self):
        return self.components.trade_manager

    @property
    def risk_manager(self):
        return self.components.risk_manager

    @property
    def fx_manager(self):
        return self.components.fx_manager

    # Market hours properties
    @property
    def market_open(self):
        return self.market_timing.market_open

    @market_open.setter
    def market_open(self, value):
        self.market_timing.market_open = value

    @property
    def market_close(self):
        return self.market_timing.market_close

    @market_close.setter
    def market_close(self, value):
        self.market_timing.market_close = value

    @property
    def base_date(self):
        return self.market_timing.base_date

    @base_date.setter
    def base_date(self, value):
        self.market_timing.base_date = value

    # User management
    def get_user_id(self) -> Optional[str]:
        with self._lock:
            return self._user_id

    def set_user_id(self, user_id: str):
        with self._lock:
            self._user_id = user_id
            self.logger.info(f"🆔 App state assigned to user: {user_id}")

    def get_base_currency(self) -> str:
        with self._lock:
            return self._base_currency

    def set_base_currency(self, currency: str):
        with self._lock:
            self._base_currency = currency

    # Configuration
    @property
    def config(self):
        return self.components.config

    def log_state_change(self, state: str):
        self.snapshot_state.log_state_change(state)


# Global app state instance
app_state = AppState()
