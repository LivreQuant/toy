# source/core/order_manager.py
import logging
import grpc
from typing import Dict, List, Optional

from source.models.order import Order
from source.models.enums import OrderSide, OrderType, OrderStatus
from source.api.grpc.conviction_exchange_interface_pb2 import (
    BatchConvictionRequest, BatchCancelRequest, ConvictionRequest, Side, ParticipationRate
)
from source.api.grpc.conviction_exchange_interface_pb2_grpc import ConvictionExchangeSimulatorStub
from source.config import config

logger = logging.getLogger('conviction_manager')

class ConvictionManager:  # Renamed from OrderManager
    def __init__(self, exchange_manager):
        self.exchange_manager = exchange_manager
        self.convictions: Dict[str, Order] = {}  # Keep using Order model internally
        self.conviction_service_url = config.order_exchange.service_url  # Keep using same config for now
        self.channel = None
        self.stub = None
        self.connected = False

    async def initialize(self):
        """Initialize the conviction manager and connect to the conviction service"""
        try:
            # Connect to the conviction exchange service
            self.channel = grpc.aio.insecure_channel(self.conviction_service_url)
            self.stub = ConvictionExchangeSimulatorStub(self.channel)
            self.connected = True
            logger.info(f"Connected to conviction exchange service at {self.conviction_service_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to conviction exchange service: {e}")
            self.connected = False
            return False

    async def cleanup(self):
        """Clean up resources"""
        if self.channel:
            await self.channel.close()
            self.channel = None
            self.stub = None
            self.connected = False
            logger.info("Disconnected from conviction exchange service")

    async def submit_conviction(
            self,
            symbol: str,
            side: OrderSide,
            quantity: float,
            order_type: OrderType,
            price: Optional[float] = None,
            score: float = 0.5,
            zscore: float = 0.0,
            participation_rate: str = "MEDIUM"
    ) -> Order:
        """Submit a new conviction through the conviction exchange service"""
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
                    order.error_message = "Conviction service unavailable"
                    return order

            # Convert to the appropriate enum values for gRPC
            side_enum = Side.BUY if side == OrderSide.BUY else Side.SELL
            
            # Map participation rate string to enum
            participation_map = {
                "LOW": ParticipationRate.LOW,
                "MEDIUM": ParticipationRate.MEDIUM,
                "HIGH": ParticipationRate.HIGH
            }
            participation_enum = participation_map.get(participation_rate, ParticipationRate.MEDIUM)

            # Create the gRPC request using conviction format
            conviction_request = ConvictionRequest(
                instrument_id=symbol,
                conviction_id=order.order_id,
                participation_rate=participation_enum,
                tag="exchange-simulator",
                side=side_enum,
                score=score,
                quantity=float(quantity),
                zscore=zscore,
                target_percentage=0.0,  # Will be calculated by conviction service
                target_notional=float(quantity * (price or 0)),
                horizon_zscore="1D"  # Default horizon
            )

            batch_request = BatchConvictionRequest(
                convictions=[conviction_request]
            )

            # Send the request
            response = await self.stub.SubmitConvictions(batch_request)

            if response.success and len(response.results) > 0:
                result = response.results[0]
                if result.success:
                    # Update the order with the response
                    order.order_id = result.broker_id or order.order_id
                    order.status = OrderStatus.FILLED  # Simplified - assume immediate fill
                    order.update(quantity, price or 0.0)
                    logger.info(f"Conviction {order.order_id} submitted successfully")
                else:
                    # Handle failure
                    order.status = OrderStatus.REJECTED
                    order.error_message = result.error_message
                    logger.warning(f"Conviction submission failed: {result.error_message}")
            else:
                # Handle batch failure
                order.status = OrderStatus.REJECTED
                order.error_message = response.error_message
                logger.warning(f"Conviction batch submission failed: {response.error_message}")

        except Exception as e:
            order.status = OrderStatus.REJECTED
            order.error_message = str(e)
            logger.error(f"Error submitting conviction: {e}")

        # Store conviction
        self.convictions[order.order_id] = order

        return order

    async def cancel_conviction(self, conviction_id: str) -> bool:
        """Cancel an existing conviction through the conviction exchange service"""
        try:
            if not self.connected:
                success = await self.initialize()
                if not success:
                    return False

            # Create the gRPC request
            request = BatchCancelRequest(
                conviction_id=[conviction_id]
            )

            # Send the request
            response = await self.stub.CancelConvictions(request)

            if response.success and len(response.results) > 0:
                result = response.results[0]
                if result.success:
                    # Update conviction status
                    logger.info(f"Conviction {conviction_id} canceled successfully")
                    return True
                else:
                    logger.warning(f"Conviction cancellation failed: {result.error_message}")
                    return False
            else:
                logger.warning(f"Conviction batch cancellation failed: {response.error_message}")
                return False

        except Exception as e:
            logger.error(f"Error canceling conviction: {e}")
            return False

    # Backward compatibility methods
    async def submit_order(self, *args, **kwargs):
        """Backward compatibility wrapper for submit_conviction"""
        return await self.submit_conviction(*args, **kwargs)
    
    async def cancel_order(self, order_id: str):
        """Backward compatibility wrapper for cancel_conviction"""
        return await self.cancel_conviction(order_id)
    
    @property
    def orders(self):
        """Backward compatibility property"""
        return self.convictions