# source/orchestration/coordination/user_context.py
from dataclasses import dataclass
from datetime import datetime

from source.orchestration.app_state.state_manager import AppState
from source.simulation.exchange.exchange_impl import Exchange
from source.simulation.core.modules.dependency_injection import ExchangeSimulatorModule


@dataclass
class UserContext:
    user_id: str
    base_currency: str
    app_state: AppState
    exchange: Exchange


def initialize_user_context(user_id: str, user_config: dict, last_snap_time: datetime, market_hours_utc: dict):
    """Initialize a single user's context"""

    # Each user gets their own app_state instance
    user_app_state = AppState()
    user_app_state.set_base_date(last_snap_time)  # Already in UTC
    user_app_state._base_currency = user_config['base_currency']
    user_app_state.set_user_id(user_id)

    # Set market hours in UTC
    user_app_state.market_open = market_hours_utc['open_utc']
    user_app_state.market_close = market_hours_utc['close_utc']

    # Each user gets their own exchange instance
    user_exchange = Exchange()

    # Set up exchange module for this user
    module = ExchangeSimulatorModule(user_exchange)
    module.configure()
    user_app_state.module = module
    user_app_state.exchange = user_exchange

    # Set exchange in equity manager
    user_app_state.equity_manager.set_exchange(user_exchange)

    # Create user context
    return UserContext(
        user_id=user_id,
        base_currency=user_config['base_currency'],
        app_state=user_app_state,
        exchange=user_exchange
    )