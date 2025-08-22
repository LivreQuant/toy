# universe.py
from threading import RLock
from typing import Dict, Optional, Callable
import logging
from source.simulation.managers.utils import CallbackManager


class UniverseManager(CallbackManager[Dict[str, Dict]]):
    def __init__(self, tracking: bool = False):
        # Universe is global data, not book-specific, so don't inherit from FileTrackingManager
        CallbackManager.__init__(self)

        self._lock = RLock()
        self._universe: Dict[str, Dict] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

        # Universe doesn't need file tracking since it's loaded once from last snapshot
        # and doesn't change during live operation
        self.tracking = tracking

    def set_universe(self, universe_data: Dict) -> None:
        """Set universe data from last snapshot - no file writing needed"""
        try:
            with self._lock:
                if 'symbols' in universe_data:
                    self._universe = universe_data['symbols']
                    self.logger.info(f"✅ Universe set with {len(self._universe)} symbols")

            self._notify_callbacks(self._universe.copy())

        except Exception as e:
            raise ValueError(f"Error setting universe: {e}")

    def is_valid_symbol(self, symbol: str) -> bool:
        """Check if a symbol is in the universe"""
        with self._lock:
            return symbol in self._universe

    def get_symbol_metadata(self, symbol: str) -> Optional[Dict]:
        """Get metadata for a symbol"""
        with self._lock:
            return self._universe.get(symbol)

    def get_all_symbols(self) -> Dict[str, Dict]:
        """Get all universe symbols and their metadata"""
        with self._lock:
            return self._universe.copy()

    def register_update_callback(self, callback: Callable[[Dict[str, Dict]], None]) -> None:
        """Alias for register_callback to maintain compatibility"""
        self.register_callback(callback)