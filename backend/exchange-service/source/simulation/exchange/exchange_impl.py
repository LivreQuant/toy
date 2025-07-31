from typing import Dict, List
import logging
from threading import RLock

from source.simulation.core.interfaces.exchange import Exchange_ABC
from source.simulation.core.interfaces.market import Market_ABC
from source.simulation.exchange.market_impl import Market

logger = logging.getLogger(__name__)


class Exchange(Exchange_ABC):
    _instance = None
    _lock = RLock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Exchange, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if not self._initialized:  # Only initialize once
            super().__init__()
            self.instrument_to_market: Dict[str, Market] = {}
            self._market_lock = RLock()
            self.logger = logging.getLogger(self.__class__.__name__)
            self._initialized = True

    def get_market(self, instrument: str) -> Market_ABC:
        """Get or create a VWAP market for an instrument"""
        with self._market_lock:
            if instrument not in self.instrument_to_market:
                market = Market(instrument)
                self.instrument_to_market[instrument] = market
            return self.instrument_to_market[instrument]

    def get_symbols(self) -> List[str]:
        """Get list of all active symbols"""
        with self._lock:
            return list(self.instrument_to_market.keys())

    def update_market_data(self, minute_bar: dict) -> None:
        """Update market data for a specific instrument"""
        try:
            symbol = minute_bar.get('symbol')
            if not symbol:
                raise ValueError("Missing symbol in minute bar data")

            # Use get_or_create_market instead of directly accessing dict
            market = self.get_market(symbol)

            # Get list of active orders before update
            market.update_market_state(minute_bar)

        except Exception as e:
            raise ValueError(f"Error updating market data: {e}")

    def remove_market(self, instrument: str) -> None:
        """Remove a market (mainly for testing/cleanup)"""
        with self._lock:
            if instrument in self.instrument_to_market:
                del self.instrument_to_market[instrument]

    def cleanup(self) -> None:
        """Cleanup all markets (for shutdown)"""
        with self._lock:
            self.instrument_to_market.clear()