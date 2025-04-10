import logging
import time
import grpc
import asyncio
from typing import AsyncGenerator

from source.config import config

from source.core.exchange_manager import ExchangeManager

# Import generated protobuf classes
from source.api.grpc.exchange_simulator_pb2 import (
    StreamRequest,
    HeartbeatRequest,
    HeartbeatResponse,
    ExchangeDataUpdate,
    MarketData,
    OrderData,
    Position,
    PortfolioStatus,
    SubmitOrderRequest,
    SubmitOrderResponse,
    CancelOrderRequest,
    CancelOrderResponse
)
from source.api.grpc.exchange_simulator_pb2_grpc import ExchangeSimulatorServicer
from source.api.rest.health import HealthService

logger = logging.getLogger('exchange_simulator')

class ExchangeSimulatorService(ExchangeSimulatorServicer):
    def __init__(self, exchange_manager: ExchangeManager):
        self.exchange_manager = exchange_manager
        self.last_heartbeat = time.time()
        self.heartbeat_counter = 0
        self.health_service = HealthService(exchange_manager, http_port=50056)

    # Add this method to the class
    async def start_health_service(self):
        """Start the health check HTTP server"""
        await self.health_service.setup()
        
    # Add this method as well
    async def stop_health_service(self):
        """Stop the health check HTTP server"""
        await self.health_service.shutdown()

    async def Heartbeat(self, request: HeartbeatRequest, context) -> HeartbeatResponse:
        """Handle heartbeat to maintain connection"""
        try:
            self.heartbeat_counter += 1
            current_time = int(time.time() * 1000)

            # Log periodic heartbeats
            if self.heartbeat_counter % 10 == 0:
                logger.debug(f"Received heartbeat #{self.heartbeat_counter}")

            return HeartbeatResponse(
                success=True,
                server_timestamp=current_time
            )
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return HeartbeatResponse(success=False)

    async def StreamExchangeData(
        self,
        request: StreamRequest,
        context
    ) -> AsyncGenerator[ExchangeDataUpdate, None]:
        """Stream market data, orders, and portfolio updates"""
        try:
            symbols = request.symbols

            while True:
                # Generate market data
                market_data, portfolio_data, orders_data = self.exchange_manager.generate_periodic_data(symbols)

                # Create ExchangeDataUpdate
                update = ExchangeDataUpdate(
                    timestamp=int(time.time() * 1000)
                )

                # Add market data
                for md in market_data:
                    update.market_data.append(MarketData(
                        symbol=md['symbol'],
                        bid=md['bid'],
                        ask=md['ask'],
                        bid_size=md['bid_size'],
                        ask_size=md['ask_size'],
                        last_price=md['last_price'],
                        last_size=md['last_size']
                    ))

                # Add order data
                for order in orders_data:
                    update.orders_data.append(OrderData(
                        order_id=order['order_id'],
                        symbol=order['symbol'],
                        status=order['status'],
                        filled_quantity=int(order['filled_quantity']),
                        average_price=order['average_price']
                    ))

                # Add portfolio data
                update.portfolio.CopyFrom(PortfolioStatus(
                    cash_balance=portfolio_data['cash_balance'],
                    total_value=portfolio_data['total_value'],
                    positions=[
                        Position(
                            symbol=pos['symbol'],
                            quantity=int(pos['quantity']),
                            average_cost=pos['average_cost'],
                            market_value=pos['market_value']
                        ) for pos in portfolio_data['positions']
                    ]
                ))

                yield update
                await asyncio.sleep(1)  # Update interval

        except asyncio.CancelledError:
            logger.info("Stream data generation cancelled")
        except Exception as e:
            logger.error(f"Stream data error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))

    async def SubmitOrder(
        self,
        request: SubmitOrderRequest,
        context
    ) -> SubmitOrderResponse:
        """Submit an order"""
        try:
            # Convert protobuf side and type to enum
            side = 'BUY' if request.side == SubmitOrderRequest.Side.BUY else 'SELL'
            order_type = 'MARKET' if request.type == SubmitOrderRequest.Type.MARKET else 'LIMIT'

            result = self.exchange_manager.submit_order(
                symbol=request.symbol,
                side=side,
                quantity=request.quantity,
                order_type=order_type,
                price=request.price,
                request_id=request.request_id
            )

            return SubmitOrderResponse(
                success=result['success'],
                order_id=result.get('order_id', ''),
                error_message=result.get('error_message', '')
            )
        except Exception as e:
            logger.error(f"Order submission error: {e}")
            return SubmitOrderResponse(
                success=False,
                error_message=str(e)
            )

    async def CancelOrder(
        self,
        request: CancelOrderRequest,
        context
    ) -> CancelOrderResponse:
        """Cancel an existing order"""
        try:
            result = self.exchange_manager.cancel_order(
                order_id=request.order_id,
                session_id=request.session_id
            )

            return CancelOrderResponse(
                success=result['success'],
                error_message=result.get('error_message', '')
            )
        except Exception as e:
            logger.error(f"Order cancellation error: {e}")
            return CancelOrderResponse(
                success=False,
                error_message=str(e)
            )