# source/core/exchange_manager.py
import logging
from typing import Dict, Any, List

from source.models.order import Order
from source.clients.exchange_client import ExchangeClient
from source.utils.metrics import track_order_submitted

logger = logging.getLogger('exchange_manager')


class ExchangeManager:
    """Manager for communicating with the exchange simulator"""

    def __init__(
            self,
            exchange_client: ExchangeClient
    ):
        self.exchange_client = exchange_client

    async def submit_orders_to_exchange(self, orders: List[Order], endpoint: str) -> Dict[str, Any]:
        """
        Submit orders to the exchange in batch
        
        Args:
            orders: List of orders to submit
            endpoint: Exchange endpoint
                
        Returns:
            Result from exchange
        """
        try:
            logger.info(f"Submitting {len(orders)} orders to exchange at {endpoint}")

            # Create batch request
            batch_request = {
                "orders": []
            }

            # Add each order to the batch
            for order in orders:
                order_request = {
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "quantity": order.quantity,
                    "price": order.price or 0,
                    "type": order.order_type.value,
                    "request_id": order.request_id or order.order_id
                }
                batch_request["orders"].append(order_request)

            # Call exchange client
            exchange_result = await self.exchange_client.submit_orders(batch_request, endpoint)

            if not exchange_result.get('success'):
                logger.warning(f"Batch of {len(orders)} orders rejected by exchange: {exchange_result.get('error')}")
                return exchange_result

            # Process results
            results = exchange_result.get('results', [])
            for i, result in enumerate(results):
                if result.get('success') and i < len(orders):
                    # Track order submitted to exchange
                    track_order_submitted(orders[i].order_type, orders[i].symbol, orders[i].side)

            logger.info(f"Successfully submitted {len(orders)} orders to exchange")
            return exchange_result

        except Exception as e:
            logger.error(f"Error submitting {len(orders)} orders to exchange: {e}")
            return {
                "success": False,
                "error": f"Exchange communication error: {str(e)}",
                "results": []
            }

    async def cancel_orders_on_exchange(self, orders: List[Order], endpoint: str) -> Dict[str, Any]:
        """
        Cancel orders on the exchange in batch
        
        Args:
            orders: List of orders to cancel
            endpoint: Exchange endpoint
                
        Returns:
            Result from exchange
        """
        try:
            logger.info(f"Cancelling {len(orders)} orders on exchange at {endpoint}")

            # Create batch request
            batch_request = {
                "order_ids": [order.order_id for order in orders]
            }

            # Call exchange client
            exchange_result = await self.exchange_client.cancel_orders(batch_request, endpoint)

            if not exchange_result.get('success'):
                logger.warning(
                    f"Batch of {len(orders)} cancellations rejected by exchange: {exchange_result.get('error')}")
                return exchange_result

            logger.info(f"Successfully sent cancellation for {len(orders)} orders to exchange")
            return exchange_result

        except Exception as e:
            logger.error(f"Error cancelling {len(orders)} orders on exchange: {e}")
            return {
                "success": False,
                "error": f"Exchange communication error: {str(e)}",
                "results": []
            }
