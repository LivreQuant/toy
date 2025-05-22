# source/core/exchange_manager.py
import logging
from typing import Dict, Any, List

from source.models.conviction import ConvictionData
from source.clients.exchange_client import ExchangeClient
from source.utils.metrics import track_conviction_submitted

logger = logging.getLogger('exchange_manager')


class ExchangeManager:
    """Manager for communicating with the exchange simulator"""

    def __init__(
            self,
            exchange_client: ExchangeClient
    ):
        self.exchange_client = exchange_client

    async def submit_convictions_to_exchange(self, convictions: List[ConvictionData], endpoint: str) -> Dict[str, Any]:
        """
        Submit convictions to the exchange in batch
        
        Args:
            convictions: List of convictions to submit
            endpoint: Exchange endpoint
                
        Returns:
            Result from exchange
        """
        try:
            logger.info(f"Submitting {len(convictions)} convictions to exchange at {endpoint}")

            # Create batch request
            batch_request = {
                "convictions": []
            }

            # Add each conviction to the batch
            for conviction in convictions:
                conviction_request = {
                    "symbol": conviction.symbol,
                    "side": conviction.side.value,
                    "quantity": conviction.quantity,
                    "price": conviction.price or 0,
                    "type": conviction.conviction_type.value,
                    "request_id": conviction.request_id or conviction.conviction_id
                }
                batch_request["convictions"].append(conviction_request)

            # Call exchange client
            exchange_result = await self.exchange_client.submit_convictions(batch_request, endpoint)

            if not exchange_result.get('success'):
                logger.warning(f"Batch of {len(convictions)} convictions rejected by exchange: {exchange_result.get('error')}")
                return exchange_result

            # Process results
            results = exchange_result.get('results', [])
            for i, result in enumerate(results):
                if result.get('success') and i < len(convictions):
                    # Track conviction submitted to exchange
                    track_conviction_submitted(convictions[i].conviction_type, convictions[i].symbol, convictions[i].side)

            logger.info(f"Successfully submitted {len(convictions)} convictions to exchange")
            return exchange_result

        except Exception as e:
            logger.error(f"Error submitting {len(convictions)} convictions to exchange: {e}")
            return {
                "success": False,
                "error": f"Exchange communication error: {str(e)}",
                "results": []
            }

    async def cancel_convictions_on_exchange(self, convictions: List[ConvictionData], endpoint: str) -> Dict[str, Any]:
        """
        Cancel convictions on the exchange in batch
        
        Args:
            convictions: List of convictions to cancel
            endpoint: Exchange endpoint
                
        Returns:
            Result from exchange
        """
        try:
            logger.info(f"Cancelling {len(convictions)} convictions on exchange at {endpoint}")

            # Create batch request
            batch_request = {
                "conviction_ids": [conviction.conviction_id for conviction in convictions]
            }

            # Call exchange client
            exchange_result = await self.exchange_client.cancel_convictions(batch_request, endpoint)

            if not exchange_result.get('success'):
                logger.warning(
                    f"Batch of {len(convictions)} cancellations rejected by exchange: {exchange_result.get('error')}")
                return exchange_result

            logger.info(f"Successfully sent cancellation for {len(convictions)} convictions to exchange")
            return exchange_result

        except Exception as e:
            logger.error(f"Error cancelling {len(convictions)} convictions on exchange: {e}")
            return {
                "success": False,
                "error": f"Exchange communication error: {str(e)}",
                "results": []
            }
