# source/orchestration/servers/session/state_managers/returns_state_manager.py
"""
Returns State Management Component
Extracted from session_server_impl.py to reduce file size
"""

import logging
from source.api.grpc.session_exchange_interface_pb2 import ExchangeDataUpdate, ReturnsStatus, ReturnData


class ReturnsStateManager:
    """Handles returns state operations for session server"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_current_returns_state(self, update: ExchangeDataUpdate):
        """Poll current returns state - Fixed for proto"""
        from source.orchestration.app_state.state_manager import app_state
        if not app_state.returns_manager:
            return

        try:
            returns_data = app_state.returns_manager.get_all_returns()
            update.returns.CopyFrom(self.build_returns_status(returns_data))
            self.logger.debug(f"📈 Added returns data with {len(returns_data)} records to update")
        except Exception as e:
            self.logger.error(f"Error adding returns state: {e}")

    def build_returns_status(self, returns_data) -> ReturnsStatus:
        """Build returns status from returns data - Fixed for proto"""
        returns_status = ReturnsStatus()

        for return_record in returns_data:
            return_data = ReturnData()
            return_data.category = getattr(return_record, 'category', '')
            return_data.subcategory = getattr(return_record, 'subcategory', '')
            return_data.emv = float(getattr(return_record, 'emv', 0.0))
            return_data.bmv = float(getattr(return_record, 'bmv', 0.0))
            return_data.bmv_book = float(getattr(return_record, 'bmv_book', 0.0))
            return_data.cf = float(getattr(return_record, 'cf', 0.0))
            return_data.periodic_return_subcategory = float(getattr(return_record, 'periodic_return_subcategory', 0.0))
            return_data.cumulative_return_subcategory = float(
                getattr(return_record, 'cumulative_return_subcategory', 0.0))
            return_data.contribution_percentage = float(getattr(return_record, 'contribution_percentage', 0.0))
            return_data.periodic_return_contribution = float(
                getattr(return_record, 'periodic_return_contribution', 0.0))
            return_data.cumulative_return_contribution = float(
                getattr(return_record, 'cumulative_return_contribution', 0.0))

            returns_status.returns.append(return_data)

        return returns_status