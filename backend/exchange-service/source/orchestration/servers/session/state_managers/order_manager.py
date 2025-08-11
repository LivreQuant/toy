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
        """Poll current orders state from OrderManager - FIXED for protobuf fields"""
        from source.orchestration.app_state.state_manager import app_state
        if not app_state.order_manager:
            return

        try:
            orders = app_state.order_manager.get_all_orders()
            print(f"🔥🔥🔥 COMPOSITE STATE: Found {len(orders)} orders")

            for order_id, order in orders.items():
                print(
                    f"🔥🔥🔥 COMPOSITE STATE: Order {order_id} attributes: {[attr for attr in dir(order) if not attr.startswith('_')]}")

                order_data = OrderData()
                order_data.order_id = order_id
                order_data.cl_order_id = getattr(order, 'cl_order_id', '')
                order_data.symbol = getattr(order, 'symbol', '')

                # Handle side enum properly
                side = getattr(order, 'side', '')
                order_data.side = str(side.name if hasattr(side, 'name') else side)

                # FIXED: Use correct protobuf field names
                order_data.original_qty = float(getattr(order, 'original_qty', 0.0))
                order_data.remaining_qty = float(getattr(order, 'remaining_qty', 0.0))
                order_data.completed_qty = float(getattr(order, 'completed_qty', 0.0))

                order_data.currency = getattr(order, 'currency', 'USD')
                order_data.price = float(getattr(order, 'price', 0.0))

                # Handle order type enum
                order_type = getattr(order, 'order_type', '')
                order_data.order_type = str(order_type.name if hasattr(order_type, 'name') else order_type)

                order_data.participation_rate = float(getattr(order, 'participation_rate', 0.0))

                # FIXED: Determine order status correctly
                if float(order.remaining_qty) <= 0:
                    order_data.order_state = OrderStateEnum.COMPLETED
                    print(
                        f"🔥🔥🔥 COMPOSITE STATE: Order {order_id} status COMPLETED (remaining_qty={order.remaining_qty})")
                else:
                    order_data.order_state = OrderStateEnum.WORKING
                    print(f"🔥🔥🔥 COMPOSITE STATE: Order {order_id} status WORKING (remaining_qty={order.remaining_qty})")

                # Handle timestamps
                if hasattr(order, 'submit_timestamp') and order.submit_timestamp:
                    order_data.submit_timestamp = int(order.submit_timestamp.timestamp() * 1000)
                if hasattr(order, 'start_timestamp') and order.start_timestamp:
                    order_data.start_timestamp = int(order.start_timestamp.timestamp() * 1000)

                update.orders_data.append(order_data)
                print(f"🔥🔥🔥 COMPOSITE STATE: Added order {order_id} with status {order_data.order_state}")

            print(f"🔥🔥🔥 COMPOSITE STATE: Orders FINAL - {len(orders)} orders added")

        except Exception as e:
            print(f"🔥🔥🔥 COMPOSITE STATE: Error adding orders state: {e}")
            import traceback
            print(f"🔥🔥🔥 COMPOSITE STATE: Order error traceback: {traceback.format_exc()}")