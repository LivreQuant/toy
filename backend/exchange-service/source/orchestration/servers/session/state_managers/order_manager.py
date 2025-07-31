# source/orchestration/servers/session/state_managers/order_state_manager.py
"""
Order State Management Component
Extracted from session_server_impl.py to reduce file size
"""

import logging
from source.api.grpc.session_exchange_interface_pb2 import ExchangeDataUpdate, OrderData, OrderStateEnum


class OrderStateManager:
    """Handles order state operations for session server"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_current_orders_state(self, update: ExchangeDataUpdate):
        """Poll current orders state from OrderManager - Fixed for proto"""
        from source.orchestration.app_state.state_manager import app_state
        if not app_state.order_manager:
            return

        try:
            orders = app_state.order_manager.get_all_orders()

            for order in orders.values():
                order_data = OrderData()
                order_data.order_id = getattr(order, 'order_id', '')
                order_data.cl_order_id = getattr(order, 'cl_order_id', '')
                order_data.symbol = getattr(order, 'symbol', '')

                # Fix: Handle side enum properly
                side = getattr(order, 'side', '')
                if hasattr(side, 'value'):
                    order_data.side = side.value
                else:
                    order_data.side = str(side)

                # Fix: Use correct attribute names from proto
                order_data.original_qty = float(getattr(order, 'original_qty', 0.0) or getattr(order, 'quantity', 0.0))
                order_data.remaining_qty = float(
                    getattr(order, 'remaining_qty', 0.0) or getattr(order, 'quantity', 0.0))
                order_data.completed_qty = float(
                    getattr(order, 'completed_qty', 0.0) or getattr(order, 'filled_quantity', 0.0))

                order_data.currency = getattr(order, 'currency', 'USD')
                order_data.price = float(getattr(order, 'price', 0.0) or getattr(order, 'limit_price', 0.0))

                # Fix: Convert enum to string properly
                order_type = getattr(order, 'order_type', '')
                if hasattr(order_type, 'value'):
                    order_data.order_type = order_type.value
                else:
                    order_data.order_type = str(order_type)

                order_data.participation_rate = float(getattr(order, 'participation_rate', 0.0))

                # Fix: Handle order state enum
                status = getattr(order, 'status', '')
                if hasattr(status, 'value'):
                    if status.value == 'WORKING':
                        order_data.order_state = OrderStateEnum.WORKING
                    elif status.value == 'COMPLETED':
                        order_data.order_state = OrderStateEnum.COMPLETED
                    elif status.value == 'CANCELLED':
                        order_data.order_state = OrderStateEnum.CANCELLED
                    else:
                        order_data.order_state = OrderStateEnum.WORKING
                else:
                    order_data.order_state = OrderStateEnum.WORKING

                # Fix: Timestamps
                timestamp = getattr(order, 'timestamp', None)
                if timestamp:
                    order_data.submit_timestamp = int(timestamp.timestamp() * 1000)
                    order_data.start_timestamp = int(timestamp.timestamp() * 1000)

                update.orders_data.append(order_data)  # Note: orders_data not orders

            self.logger.debug(f"📋 Added {len(orders)} orders to update")
        except Exception as e:
            self.logger.error(f"Error adding orders state: {e}")