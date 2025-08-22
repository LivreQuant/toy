# source/orchestration/coordination/book_context.py
from dataclasses import dataclass
from datetime import datetime

from source.orchestration.app_state.state_manager import AppState
from source.simulation.exchange.exchange_impl import Exchange
from source.simulation.core.modules.dependency_injection import ExchangeSimulatorModule


@dataclass
class BookContext:
    book_id: str
    timezone: str
    base_currency: str
    initial_nav: int
    operation_id: int
    engine_id: int
    app_state: AppState
    exchange: Exchange


def initialize_book_context(book_id: str, book_config: dict, last_snap_time: datetime, market_hours_utc: dict):
    """Initialize a single book's context"""

    # Each book gets their own app_state instance
    book_app_state = AppState()
    book_app_state.set_base_date(last_snap_time)  # Already in UTC
    book_app_state._timezone = book_config['timezone']
    book_app_state._base_currency = book_config['base_currency']
    book_app_state._initial_nav = book_config['initial_nav']
    book_app_state._operation_id = book_config['operation_id']
    book_app_state._engine_id = book_config['engine_id']
    book_app_state.set_book_id(book_id)

    # Set market hours in UTC
    book_app_state.market_open = market_hours_utc['open_utc']
    book_app_state.market_close = market_hours_utc['close_utc']

    # Each book gets their own exchange instance
    book_exchange = Exchange()

    # Set up exchange module for this book
    module = ExchangeSimulatorModule(book_exchange)
    module.configure()
    book_app_state.module = module
    book_app_state.exchange = book_exchange

    # Set exchange in equity manager
    book_app_state.equity_manager.set_exchange(book_exchange)

    # Create book context
    return BookContext(
        book_id=book_id,
        timezone=book_config['timezone'],
        base_currency=book_config['base_currency'],
        initial_nav=book_config['initial_nav'],
        operation_id=book_config['operation_id'],
        engine_id=book_config['engine_id'],
        app_state=book_app_state,
        exchange=book_exchange
    )