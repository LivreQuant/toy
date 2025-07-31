# source/orchestration/servers/session/state_managers/universe_state_manager.py
"""
Universe State Management Component
Extracted from session_server_impl.py to reduce file size
"""

import logging
from source.proto.session_exchange_interface_pb2 import ExchangeDataUpdate, UniverseStatus, UniverseData


class UniverseStateManager:
    """Handles universe state operations for session server"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_current_universe_state(self, update: ExchangeDataUpdate):
        """Poll current universe state - Fixed for proto"""
        from source.orchestration.app_state.state_manager import app_state
        if not app_state.universe_manager:
            return

        try:
            universe = app_state.universe_manager.get_all_symbols()
            update.universe.CopyFrom(self.build_universe_status(universe))
            self.logger.debug(f"🌐 Added universe with {len(universe)} symbols to update")
        except Exception as e:
            self.logger.error(f"Error adding universe state: {e}")

    def build_universe_status(self, universe) -> UniverseStatus:
        """Build universe status from universe data"""
        universe_status = UniverseStatus()

        for symbol_data in universe.values():
            universe_data = UniverseData()
            universe_data.symbol = symbol_data['symbol']
            universe_data.sector = symbol_data['sector']
            universe_data.industry = symbol_data['industry']
            universe_data.market_cap = symbol_data['market_cap']
            universe_data.country = symbol_data['country']
            universe_data.currency = symbol_data['currency']
            universe_data.avg_daily_volume = symbol_data['avg_daily_volume']
            universe_data.beta = symbol_data['beta']

            # Add exposures
            if 'exposures' in symbol_data:
                for key, value in symbol_data['exposures'].items():
                    universe_data.exposures[key] = value

            # Add custom attributes
            if 'custom_attributes' in symbol_data:
                for key, value in symbol_data['custom_attributes'].items():
                    universe_data.custom_attributes[key] = str(value)

            universe_status.symbols.append(universe_data)

        return universe_status