# source/core/order_manager.py
import logging
import grpc
from typing import Dict, List, Optional

from source.models.order import Order
from source.models.enums import OrderSide, OrderType, OrderStatus
from source.api.grpc.order_exchange_interface_pb2 import BatchOrderRequest, BatchCancelRequest, OrderRequest
from source.api.grpc.order_exchange_interface_pb2_grpc import OrderExchangeSimulatorStub
from source.config import config

logger = logging.getLogger('order_manager')

class OrderManager:
    def __init__(self, exchange_manager):
        self.exchange_manager = exchange_manager
        self.orders: Dict[str, Order] = {}
        self.order_service_url = config.order_exchange.service_url
        self.channel = None
        self.stub = None
        self.connected = False

    async def initialize(self):
        """Initialize the order manager and connect to the order service"""
        try:
            # Connect to the order exchange service
            self.channel = grpc.aio.insecure_channel(self.order_service_url)
            self.stub = OrderExchangeSimulatorStub(self.channel)
            self.connected = True
            logger.info(f"Connected to order exchange service at {self.order_service_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to order exchange service: {e}")
            self.connected = False
            return False

    async def cleanup(self):
        """Clean up resources"""
        if self.channel:
            await self.channel.close()
            self.channel = None
            self.stub = None
            self.connected = False
            logger.info("Disconnected from order exchange service")

    async def submit_order(
            self,
            symbol: str,
            side: OrderSide,
            quantity: float,
            order_type: OrderType,
            price: Optional[float] = None
    ) -> Order:
        """Submit a new order through the order exchange service"""
        order = Order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price
        )

        try:
            if not self.connected:
                success = await self.initialize()
                if not success:
                    order.status = OrderStatus.REJECTED
                    order.error_message = "Order service unavailable"
                    return order

            # Convert to the appropriate enum values for gRPC
            side_enum = 0 if side == OrderSide.BUY else 1
            type_enum = 0 if order_type == OrderType.MARKET else 1

            # Create the gRPC request
            order_request = OrderRequest(
                symbol=symbol,
                side=side_enum,
                quantity=float(quantity),
                price=float(price) if price is not None else 0.0,
                type=type_enum,
                request_id=order.order_id
            )

            batch_request = BatchOrderRequest(
                orders=[order_request]
            )

            # Send the request
            response = await self.stub.SubmitOrders(batch_request)

            if response.success and len(response.results) > 0:
                result = response.results[0]
                if result.success:
                    # Update the order with the response
                    order.order_id = result.order_id
                    order.status = OrderStatus.FILLED  # Simplified - assume immediate fill
                    order.update(quantity, price or 0.0)
                    logger.info(f"Order {order.order_id} submitted successfully")
                else:
                    # Handle failure
                    order.status = OrderStatus.REJECTED
                    order.error_message = result.error_message
                    logger.warning(f"Order submission failed: {result.error_message}")
            else:
                # Handle batch failure
                order.status = OrderStatus.REJECTED
                order.error_message = response.error_message
                logger.warning(f"Order batch submission failed: {response.error_message}")

        except Exception as e:
            order.status = OrderStatus.REJECTED
            order.error_message = str(e)
            logger.error(f"Error submitting order: {e}")

        # Store order
        self.orders[order.order_id] = order

        return order

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order through the order exchange service"""
        try:
            if not self.connected:
                success = await self.initialize()
                if not success:
                    return False

            # Create the gRPC request
            request = BatchCancelRequest(
                order_ids=[order_id]
            )

            # Send the request
            response = await self.stub.CancelOrders(request)

            if response.success and len(response.results) > 0:
                result = response.results[0]
                if result.success:
                    # Update order status
                    logger.info(f"Order {order_id} canceled successfully")
                    return True
                else:
                    logger.warning(f"Order cancellation failed: {result.error_message}")
                    return False
            else:
                logger.warning(f"Order batch cancellation failed: {response.error_message}")
                return False

        except Exception as e:
            logger.error(f"Error canceling order: {e}")
            return False