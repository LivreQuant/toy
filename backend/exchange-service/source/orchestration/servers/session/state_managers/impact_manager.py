# source/orchestration/servers/session/state_managers/impact_state_manager.py
"""
Impact State Management Component - FIXED
"""

import traceback
import logging
from source.api.grpc.session_exchange_interface_pb2 import ExchangeDataUpdate, ImpactStatus, ImpactData


class ImpactStateManager:
    """Handles impact state operations for session server"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_current_impact_state(self, update: ExchangeDataUpdate):
        """Poll current impact state - FIXED to handle ImpactState objects"""
        from source.orchestration.app_state.state_manager import app_state
        if not app_state.impact_manager:
            print(f"🔥🔥🔥 COMPOSITE STATE: No impact_manager available")
            return

        try:
            # Get all impact states from ImpactManager
            impact_states = app_state.impact_manager.get_all_impacts()
            print(f"🔥🔥🔥 COMPOSITE STATE: Found {len(impact_states)} impact states")

            for symbol, impact_state in impact_states.items():
                print(f"🔥🔥🔥 COMPOSITE STATE: Impact {symbol} state type: {type(impact_state)}")
                print(
                    f"🔥🔥🔥 COMPOSITE STATE: Impact {symbol} attributes: {[attr for attr in dir(impact_state) if not attr.startswith('_')]}")

                impact_data = ImpactData()

                # FIXED: Access ImpactState object attributes correctly
                impact_data.symbol = symbol
                impact_data.current_impact = float(getattr(impact_state, 'current_impact', 0.0))
                impact_data.currency = getattr(impact_state, 'currency', 'USD')
                impact_data.base_price = float(getattr(impact_state, 'base_price', 0.0))
                impact_data.impacted_price = float(getattr(impact_state, 'impacted_price', 0.0))

                # Handle volume fields (convert to int)
                impact_data.cumulative_volume = int(getattr(impact_state, 'cumulative_volume', 0))
                impact_data.trade_volume = int(getattr(impact_state, 'trade_volume', 0))

                update.impact.impacts.append(impact_data)

                print(f"🔥🔥🔥 COMPOSITE STATE: Added impact {symbol}")
                print(f"🔥🔥🔥 COMPOSITE STATE: - current_impact: {impact_data.current_impact}")
                print(f"🔥🔥🔥 COMPOSITE STATE: - base_price: {impact_data.base_price}")
                print(f"🔥🔥🔥 COMPOSITE STATE: - impacted_price: {impact_data.impacted_price}")
                print(f"🔥🔥🔥 COMPOSITE STATE: - trade_volume: {impact_data.trade_volume}")

            print(f"🔥🔥🔥 COMPOSITE STATE: Impact FINAL - {len(impact_states)} impacts added")
            self.logger.debug(f"💥 Added impact data with {len(impact_states)} impacts to update")

        except Exception as e:
            print(f"🔥🔥🔥 COMPOSITE STATE: Error adding impact state: {e}")
            print(f"🔥🔥🔥 COMPOSITE STATE: Impact error traceback: {traceback.format_exc()}")
            self.logger.error(f"Error adding impact state: {e}")