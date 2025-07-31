# source/orchestration/servers/session/state_managers/impact_state_manager.py
"""
Impact State Management Component
Extracted from session_server_impl.py to reduce file size
"""

import logging
from source.api.grpc.session_exchange_interface_pb2 import ExchangeDataUpdate, ImpactStatus, ImpactData


class ImpactStateManager:
    """Handles impact state operations for session server"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_current_impact_state(self, update: ExchangeDataUpdate):
        """Poll current impact state - Fixed for proto"""
        from source.orchestration.app_state.state_manager import app_state
        if not app_state.impact_manager:
            return

        try:
            impact_data = app_state.impact_manager.get_all_impacts()
            update.impact.CopyFrom(self.build_impact_status(impact_data))
            self.logger.debug(f"💥 Added impact data with {len(impact_data)} impacts to update")
        except Exception as e:
            self.logger.error(f"Error adding impact state: {e}")

    def build_impact_status(self, impact_data) -> ImpactStatus:
        """Build impact status from impact data - Fixed for proto"""
        impact_status = ImpactStatus()

        for impact_record in impact_data:
            impact = ImpactData()
            impact.symbol = getattr(impact_record, 'symbol', '')
            impact.current_impact = float(getattr(impact_record, 'current_impact', 0.0))
            impact.currency = getattr(impact_record, 'currency', 'USD')
            impact.base_price = float(getattr(impact_record, 'base_price', 0.0))

            # FIX: Convert to integers for volume fields
            if hasattr(impact, 'cumulative_volume'):
                impact.cumulative_volume = int(getattr(impact_record, 'cumulative_volume', 0))
            if hasattr(impact, 'trade_volume'):
                impact.trade_volume = int(getattr(impact_record, 'trade_volume', 0))

            # FIX: Only set fields that exist in the proto
            if hasattr(impact, 'impacted_price'):
                impact.impacted_price = float(getattr(impact_record, 'impacted_price', 0.0))

            impact_status.impacts.append(impact)

        return impact_status