# source/api/service.py
import logging
import time
import grpc
import asyncio
from typing import AsyncGenerator

from source.config import config
from source.core.exchange_manager import ExchangeManager

# Import generated protobuf classes
from source.api.grpc.session_exchange_interface_pb2 import (
    StreamRequest,
    HeartbeatRequest,
    HeartbeatResponse,
    ExchangeDataUpdate,
    MarketData,
    OrderData,
    Position,
    PortfolioStatus
)
from source.api.grpc.session_exchange_interface_pb2_grpc import SessionExchangeSimulatorServicer
from source.api.grpc.order_exchange_interface_pb2 import (
    SubmitOrderRequest,
    SubmitOrderResponse,
    CancelOrderRequest, 
    CancelOrderResponse
)
from source.api.grpc.order_exchange_interface_pb2_grpc import OrderExchangeSimulatorServicer
from source.api.rest.health import HealthService

logger = logging.getLogger('exchange_simulator')


class ExchangeSimulatorService(SessionExchangeSimulatorServicer, OrderExchangeSimulatorServicer):
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

    async def receive_market_data(self, market_data_list):
        """
        Process received market data from distributor
        
        Args:
            market_data_list: List of market data updates
        """
        try:
            # Update the exchange manager with the new market data
            self.exchange_manager.update_market_data(market_data_list)
            logger.info(f"Received market data for {len(market_data_list)} symbols")
            return True
        except Exception as e:
            logger.error(f"Error processing market data: {e}")
            return False
        
    async def StreamExchangeData(
            self,
            request: StreamRequest,
            context
    ) -> AsyncGenerator[ExchangeDataUpdate, None]:
        """Stream market data, orders, and portfolio updates"""
        try:
            client_id = request.client_id
            symbols = request.symbols
        
            logger.info(f"Client {client_id} subscribed to exchange data stream for symbols: {symbols}")
            
            update_count = 0
            while True:
                # Generate market data
                market_data, portfolio_data, orders_data = self.exchange_manager.generate_periodic_data(symbols)

                # Log periodically to avoid flooding logs
                update_count += 1
                logger.info(f"Sending update #{update_count} to client {client_id} for {len(market_data)} symbols")

                # Create ExchangeDataUpdate
                update = ExchangeDataUpdate(
                    timestamp=int(time.time() * 1000)
                )

                # Add market data (updated for minute bars)
                for md in market_data:
                    update.market_data.append(MarketData(
                        symbol=md['symbol'],
                        open=md['open'],
                        high=md['high'],
                        low=md['low'],
                        close=md['close'],
                        volume=md['volume'],
                        trade_count=md.get('trade_count', 0),
                        vwap=md.get('vwap', 0.0)
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

                # Send the update
                yield update

                # Sleep for 60 seconds (1 minute) before generating the next update
                await asyncio.sleep(60)  # Update interval

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
