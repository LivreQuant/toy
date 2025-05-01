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
    OrderResponse,
    BatchOrderResponse,
    CancelResult,
    BatchCancelResponse
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
   
    async def SubmitOrders(self, request, context):
        """
        Handle batch order submissions
        """
        try:
            # Create response object
            response = BatchOrderResponse(
                success=True,
                results=[]
            )
            
            # Process each order in the batch
            for order_request in request.orders:
                # Extract order parameters
                symbol = order_request.symbol
                side = "BUY" if order_request.side == 0 else "SELL"
                quantity = order_request.quantity
                price = order_request.price if order_request.type == 1 else None  # Only for LIMIT
                order_type = "MARKET" if order_request.type == 0 else "LIMIT"
                request_id = order_request.request_id
                
                # Submit to exchange manager
                order_result = await self.exchange_manager.submit_order(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    order_type=order_type,
                    price=price,
                    request_id=request_id
                )
                
                # Create result for this order
                if order_result.get('success'):
                    result = OrderResponse(
                        success=True,
                        order_id=order_result.get('order_id', '')
                    )
                else:
                    result = OrderResponse(
                        success=False,
                        order_id='',
                        error_message=order_result.get('error_message', 'Order submission failed')
                    )
                    
                response.results.append(result)
                
            return response
            
        except Exception as e:
            logger.error(f"Error processing batch order submission: {e}")
            
            # Return error response
            return BatchOrderResponse(
                success=False,
                error_message=f"Server error: {str(e)}",
                results=[]
            )
            
    async def CancelOrders(self, request, context):
        """
        Handle batch order cancellations
        """
        try:
            # Create response object
            response = BatchCancelResponse(
                success=True,
                results=[]
            )
            
            # Process each order ID in the batch
            for order_id in request.order_ids:
                # Cancel the order
                cancel_result = await self.exchange_manager.cancel_order(
                    order_id=order_id
                )
                
                # Create result for this cancellation
                result = CancelResult(
                    order_id=order_id,
                    success=cancel_result.get('success', False)
                )
                
                if not cancel_result.get('success'):
                    result.error_message = cancel_result.get('error_message', 'Order cancellation failed')
                    
                response.results.append(result)
                
            return response
            
        except Exception as e:
            logger.error(f"Error processing batch order cancellation: {e}")
            
            # Return error response
            return BatchCancelResponse(
                success=False,
                error_message=f"Server error: {str(e)}",
                results=[]
            )