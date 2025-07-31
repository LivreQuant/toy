# source/orchestration/servers/session/state_managers/fx_state_manager.py
"""
FX State Management Component
Extracted from session_server_impl.py to reduce file size
"""

import logging
from source.proto.session_exchange_interface_pb2 import ExchangeDataUpdate, FXStatus, FXRate


class FXStateManager:
    """Handles FX state operations for session server"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_current_fx_state(self, update: ExchangeDataUpdate):
        """Poll current FX state - Fixed for proto"""
        from source.orchestration.app_state.state_manager import app_state
        if not app_state.fx_manager:
            return

        try:
            rates = app_state.fx_manager.get_all_rates()
            update.fx_rates.CopyFrom(self.build_fx_status(rates))
            self.logger.debug(f"💱 Added {len(rates)} FX rates to update")
        except Exception as e:
            self.logger.error(f"Error adding FX state: {e}")

    def build_fx_status(self, rates) -> FXStatus:
        """Build FX status from rates - Fixed for proto"""
        fx_status = FXStatus()

        for rate_pair, rate_data in rates.items():
            fx_rate = FXRate()

            # Fix: Use correct field names from proto
            currencies = rate_pair.split('/')
            if len(currencies) == 2:
                fx_rate.from_currency = currencies[0]
                fx_rate.to_currency = currencies[1]
            else:
                fx_rate.from_currency = rate_pair
                fx_rate.to_currency = 'USD'

            if isinstance(rate_data, dict):
                fx_rate.rate = float(rate_data.get('rate', 1.0))
            else:
                fx_rate.rate = float(getattr(rate_data, 'rate', 1.0))

            fx_status.rates.append(fx_rate)

        return fx_status