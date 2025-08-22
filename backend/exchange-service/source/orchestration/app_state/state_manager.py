# source/orchestration/app_state/state_manager.py
"""
Main State Manager - Coordination only
"""
import logging
from threading import RLock
from typing import Optional, Dict, Any
from datetime import datetime

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

        # book context only
        self._book_id: Optional[str] = None

        # Parameters
        self._base_currency = 'USD'
        self._timezone = 'America/New_York'
        self._initial_nav = 100000000
        self._opertion_id = 0
        self._engine_id = 1

        # State tracking
        self._last_update_time = datetime.now()
        self._initialization_complete = False

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
        with self._lock:
            return self.components.is_initialized() and self._initialization_complete

    def mark_initialization_complete(self) -> None:
        """Mark initialization as complete"""
        with self._lock:
            self._initialization_complete = True
            self.logger.info("✅ App state initialization marked complete")

    def is_healthy(self) -> bool:
        return self.service_health.is_healthy()

    def request_shutdown(self) -> None:
        """Request system shutdown"""
        self.service_health.shutdown_all_services()
        self.components.shutdown_all_managers()

    # Snapshot state delegation - ALL METHODS
    def mark_last_snap_universe_received(self):
        self.snapshot_state.mark_universe_received()
        self._update_last_update_time()

    def mark_last_snap_portfolio_received(self):
        self.snapshot_state.mark_portfolio_received()
        self._update_last_update_time()

    def mark_last_snap_orders_received(self):
        self.snapshot_state.mark_orders_received()
        self._update_last_update_time()

    def mark_last_snap_accounts_received(self):
        self.snapshot_state.mark_accounts_received()
        self._update_last_update_time()

    def mark_last_snap_account_received(self):
        """Missing method - same as accounts"""
        self.snapshot_state.mark_accounts_received()
        self._update_last_update_time()

    def mark_last_snap_equity_received(self):
        self.snapshot_state.mark_equity_received()
        self._update_last_update_time()

    def mark_last_snap_fx_received(self):
        self.snapshot_state.mark_fx_received()
        self._update_last_update_time()

    def mark_last_snap_impact_received(self):
        self.snapshot_state.mark_impact_received()
        self._update_last_update_time()

    def mark_last_snap_returns_received(self):
        self.snapshot_state.mark_returns_received()
        self._update_last_update_time()

    def mark_last_snap_risk_received(self):
        self.snapshot_state.mark_risk_received()
        self._update_last_update_time()

    def mark_last_snap_trades_received(self):
        self.snapshot_state.mark_trades_received()
        self._update_last_update_time()

    def mark_last_snap_conviction_received(self):
        self.snapshot_state.mark_conviction_received()
        self._update_last_update_time()

    def mark_last_snap_cash_flow_received(self):
        self.snapshot_state.mark_cash_flow_received()
        self._update_last_update_time()

    def _update_last_update_time(self):
        """Update the last update timestamp"""
        with self._lock:
            self._last_update_time = datetime.now()

    def get_last_update_time(self) -> datetime:
        """Get the last update timestamp"""
        with self._lock:
            return self._last_update_time

    # Market timing delegation
    def get_current_timestamp(self):
        return self.market_timing.get_current_timestamp()

    def get_next_timestamp(self):
        return self.market_timing.get_next_timestamp()

    def set_current_timestamp(self, timestamp):
        self.market_timing.set_current_timestamp(timestamp)
        self._update_last_update_time()

    def is_market_open(self):
        return self.market_timing.is_market_open()

    @property
    def current_timestamp(self):
        return self.market_timing.current_timestamp

    @current_timestamp.setter
    def current_timestamp(self, value):
        self.market_timing.current_timestamp = value
        self._update_last_update_time()

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

    def set_base_date(self, value):
        """Set the base date - missing method that was causing the error"""
        self.market_timing.base_date = value
        self.logger.debug(f"📅 Base date set to: {value}")

    # CRITICAL: Add missing _received_first_market_data property
    @property
    def _received_first_market_data(self):
        """Delegate to market timing"""
        return self.market_timing._received_first_market_data

    @_received_first_market_data.setter
    def _received_first_market_data(self, value):
        """Delegate to market timing"""
        self.market_timing._received_first_market_data = value

    def mark_first_market_data_received(self, timestamp):
        self.market_timing.mark_first_market_data_received(timestamp)
        self._update_last_update_time()

    def initialize_bin(self, timestamp):
        self.market_timing.initialize_bin(timestamp)
        self._update_last_update_time()

    def advance_bin(self):
        self.market_timing.advance_bin()
        self._update_last_update_time()

    def get_current_bin(self):
        return self.market_timing.get_current_bin()

    def get_next_bin(self):
        return self.market_timing.get_next_bin()

    # Service health delegation
    def mark_service_started(self, service_name: str):
        self.service_health.mark_service_started(service_name)

    def mark_service_stopped(self, service_name: str):
        self.service_health.mark_service_stopped(service_name)

    def is_service_running(self, service_name: str) -> bool:
        return self.service_health.is_service_running(service_name)

    def get_health_status(self) -> Dict[str, Any]:
        return self.service_health.get_health_status()

    def get_service_status(self, service_name: str) -> str:
        return self.service_health.get_service_status(service_name)

    # book management
    def get_book_id(self) -> Optional[str]:
        with self._lock:
            return self._book_id

    def set_book_id(self, book_id: str):
        with self._lock:
            old_book_id = self._book_id
            self._book_id = book_id

            # Set book context in all managers
            self.components.set_book_context(book_id)

            self.logger.info(f"🆔 App state assigned to book: {book_id}")
            if old_book_id and old_book_id != book_id:
                self.logger.info(f"🔄 book context changed from {old_book_id} to {book_id}")

    def clear_book_context(self):
        """Clear book context"""
        with self._lock:
            old_book_id = self._book_id
            self._book_id = None
            self.logger.info(f"🧹 Cleared book context (was: {old_book_id})")

    # Component manager delegation
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

    # Business logic managers
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

    # Parameter management
    def get_base_currency(self) -> str:
        with self._lock:
            return self._base_currency

    def set_base_currency(self, currency: str):
        with self._lock:
            self._base_currency = currency
            self.logger.debug(f"💰 Base currency set to: {currency}")

    def get_initial_nav(self) -> int:
        with self._lock:
            return self._initial_nav

    def set_initial_nav(self, initial_nav: int):
        with self._lock:
            self._initial_nav = initial_nav
            self.logger.debug(f"💰 Initial NAV set to: {initial_nav}")

    def get_timezone(self) -> str:
        with self._lock:
            return self._timezone

    def set_timezone(self, timezone: str):
        with self._lock:
            self._timezone = timezone
            self.logger.debug(f"🕐 Timezone set to: {timezone}")

    def get_opertion_id(self) -> int:
        with self._lock:
            return self._opertion_id

    def set_opertion_id(self, opertion_id: int):
        with self._lock:
            self._opertion_id = opertion_id
            self.logger.debug(f"🔧 Operation ID set to: {opertion_id}")

    def get_engine_id(self) -> int:
        with self._lock:
            return self._engine_id

    def set_engine_id(self, engine_id: int):
        with self._lock:
            self._engine_id = engine_id
            self.logger.debug(f"⚙️ Engine ID set to: {engine_id}")

    # Configuration
    @property
    def config(self):
        return self.components.config

    def log_state_change(self, state: str):
        self.snapshot_state.log_state_change(state)
        self._update_last_update_time()

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        with self._lock:
            return {
                'app_state': self.get_app_state(),
                'current_state': self.get_current_state(),
                'book_id': self._book_id,
                'initialized': self.is_initialized(),
                'healthy': self.is_healthy(),
                'last_update': self._last_update_time.isoformat(),
                'market_open': self.is_market_open(),
                'current_timestamp': self.get_current_timestamp().isoformat() if self.get_current_timestamp() else None,
                'base_currency': self._base_currency,
                'timezone': self._timezone,
                'engine_id': self._engine_id,
                'services': self.get_health_status(),
                'managers': self.components.get_manager_status()
            }

    def validate_system(self) -> Dict[str, Any]:
        """Validate entire system"""
        with self._lock:
            validation = {
                'valid': True,
                'errors': [],
                'warnings': [],
                'components': {}
            }

            # Validate components
            try:
                component_validation = self.components.validate_managers()
                validation['components'] = component_validation

                # Check for any invalid managers
                for manager_name, manager_validation in component_validation.items():
                    if not manager_validation.get('valid', True):
                        validation['valid'] = False
                        validation['errors'].append(f"Manager {manager_name} validation failed")

            except Exception as e:
                validation['valid'] = False
                validation['errors'].append(f"Component validation error: {e}")

            # Validate book context
            if not self._book_id:
                validation['warnings'].append("No book context set")

            # Validate initialization
            if not self._initialization_complete:
                validation['warnings'].append("Initialization not marked complete")

            return validation

    def reset_system(self) -> None:
        """Reset entire system to initial state"""
        with self._lock:
            self.logger.info("🔄 Resetting entire system...")

            # Reset all components
            self.snapshot_state = SnapshotState()
            self.market_timing = MarketTiming()
            self.service_health = ServiceHealth()
            self.components.reset_all_managers()

            # Reset parameters
            self._book_id = None
            self._base_currency = 'USD'
            self._timezone = 'America/New_York'
            self._initial_nav = 100000000
            self._opertion_id = 0
            self._engine_id = 1
            self._last_update_time = datetime.now()
            self._initialization_complete = False

            self.logger.info("✅ System reset complete")


# Global app state instance
app_state = AppState()