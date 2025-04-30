import logging
from typing import Dict, Any

from source.models.order import Order
from source.models.enums import OrderStatus
from source.clients.exchange_client import ExchangeClient
from source.utils.metrics import track_order_submitted, track_order_status_change

logger = logging.getLogger('exchange_manager')


class ExchangeManager:
    """Manager for communicating with the exchange simulator"""

    def __init__(
            self,
            exchange_client: ExchangeClient
    ):
        self.exchange_client = exchange_client

    async def submit_order_to_exchange(self, order: Order, endpoint: str) -> Dict[str, Any]:
        """
        Submit an order to the exchange
        
        Args:
            order: Order to submit
            endpoint: Exchange endpoint
            
        Returns:
            Result from exchange
        """
        try:
            logger.info(f"Submitting order {order.order_id} to exchange at {endpoint}")

            # Call exchange client
            exchange_result = await self.exchange_client.submit_order(order, endpoint)

            if not exchange_result.get('success'):
                logger.warning(f"Order {order.order_id} rejected by exchange: {exchange_result.get('error')}")
                return exchange_result

            # Track order submitted to exchange
            track_order_submitted(order.order_type, order.symbol, order.side)

            # Update order ID if exchange assigned a different one
            if (exchange_result.get('order_id') and
                    exchange_result.get('order_id') != order.order_id):
                exchange_result['original_order_id'] = order.order_id
                logger.info(f"Exchange assigned new order ID: {exchange_result.get('order_id')}")

            logger.info(f"Order {order.order_id} successfully submitted to exchange")
            return exchange_result

        except Exception as e:
            logger.error(f"Error submitting order {order.order_id} to exchange: {e}")
            return {
                "success": False,
                "error": f"Exchange communication error: {str(e)}",
                "order_id": order.order_id
            }

    async def cancel_order_on_exchange(self, order: Order, endpoint: str) -> Dict[str, Any]:
        """
        Cancel an order on the exchange
        
        Args:
            order: Order to cancel
            endpoint: Exchange endpoint
            
        Returns:
            Result from exchange
        """
        try:
            logger.info(f"Cancelling order {order.order_id} on exchange at {endpoint}")

            # Call exchange client
            exchange_result = await self.exchange_client.cancel_order(order, endpoint)

            if not exchange_result.get('success'):
                logger.warning(f"Failed to cancel order {order.order_id} on exchange: {exchange_result.get('error')}")
                return exchange_result

            # Track status change
            track_order_status_change(order.status.value, OrderStatus.CANCELED.value)

            logger.info(f"Order {order.order_id} successfully cancelled on exchange")
            return exchange_result

        except Exception as e:
            logger.error(f"Error cancelling order {order.order_id} on exchange: {e}")
            return {
                "success": False,
                "error": f"Exchange communication error: {str(e)}"
            }
