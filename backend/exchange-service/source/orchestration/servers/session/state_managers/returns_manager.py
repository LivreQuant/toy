# source/orchestration/servers/session/state_managers/returns_state_manager.py
"""
Returns State Management Component - FIXED
"""

import traceback
import logging
from source.api.grpc.session_exchange_interface_pb2 import ExchangeDataUpdate, ReturnsStatus, ReturnData


class ReturnsStateManager:
    """Handles returns state operations for session server"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_current_returns_state(self, update: ExchangeDataUpdate):
        """Poll current returns state - FIXED to handle nested dictionary structure"""
        from source.orchestration.app_state.state_manager import app_state
        if not app_state.returns_manager:
            print(f"🔥🔥🔥 COMPOSITE STATE: No returns_manager available")
            return

        try:
            # Get all returns - this is a nested dict: {category: {subcategory: ReturnMetrics}}
            returns_data = app_state.returns_manager.get_all_returns()
            print(f"🔥🔥🔥 COMPOSITE STATE: Found {len(returns_data)} return categories")

            for category, subcategories in returns_data.items():
                print(f"🔥🔥🔥 COMPOSITE STATE: Return category '{category}' has {len(subcategories)} subcategories")

                for subcategory, return_metrics in subcategories.items():
                    print(f"🔥🔥🔥 COMPOSITE STATE: Return {category}/{subcategory} metrics type: {type(return_metrics)}")
                    print(
                        f"🔥🔥🔥 COMPOSITE STATE: Return {category}/{subcategory} attributes: {[attr for attr in dir(return_metrics) if not attr.startswith('_')]}")

                    return_data = ReturnData()

                    # FIXED: Access ReturnMetrics object attributes correctly
                    return_data.symbol = getattr(return_metrics, 'symbol',
                                                 subcategory)  # Use subcategory as symbol fallback
                    return_data.return_value = float(getattr(return_metrics, 'periodic_return_subcategory', 0.0))
                    return_data.currency = getattr(return_metrics, 'currency', 'USD')
                    return_data.category = category
                    return_data.subcategory = subcategory
                    return_data.emv = float(getattr(return_metrics, 'emv', 0.0))
                    return_data.bmv = float(getattr(return_metrics, 'bmv', 0.0))
                    return_data.bmv_book = float(getattr(return_metrics, 'bmv_book', 0.0))
                    return_data.cf = float(getattr(return_metrics, 'cf', 0.0))
                    return_data.periodic_return_subcategory = float(
                        getattr(return_metrics, 'periodic_return_subcategory', 0.0))
                    return_data.cumulative_return_subcategory = float(
                        getattr(return_metrics, 'cumulative_return_subcategory', 0.0))
                    return_data.contribution_percentage = float(getattr(return_metrics, 'contribution_percentage', 0.0))
                    return_data.periodic_return_contribution = float(
                        getattr(return_metrics, 'periodic_return_contribution', 0.0))
                    return_data.cumulative_return_contribution = float(
                        getattr(return_metrics, 'cumulative_return_contribution', 0.0))

                    update.returns.returns.append(return_data)

                    print(f"🔥🔥🔥 COMPOSITE STATE: Added return {category}/{subcategory}")
                    print(f"🔥🔥🔥 COMPOSITE STATE: - emv: {return_data.emv}")
                    print(f"🔥🔥🔥 COMPOSITE STATE: - bmv: {return_data.bmv}")
                    print(f"🔥🔥🔥 COMPOSITE STATE: - periodic_return: {return_data.periodic_return_subcategory}")
                    print(f"🔥🔥🔥 COMPOSITE STATE: - contribution_pct: {return_data.contribution_percentage}")

            total_returns = sum(len(subcats) for subcats in returns_data.values())
            print(f"🔥🔥🔥 COMPOSITE STATE: Returns FINAL - {total_returns} returns added")
            self.logger.debug(f"📈 Added returns data with {total_returns} records to update")

        except Exception as e:
            print(f"🔥🔥🔥 COMPOSITE STATE: Error adding returns state: {e}")
            print(f"🔥🔥🔥 COMPOSITE STATE: Returns error traceback: {traceback.format_exc()}")
            self.logger.error(f"Error adding returns state: {e}")