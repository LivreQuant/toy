# source/api/service.py
import logging
import time
import grpc
import uuid
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
        self.health_service = exchange_manager.get_health_service() if hasattr(exchange_manager, 'get_health_service') else HealthService(exchange_manager, http_port=50056)
        self.startup_time = time.time()

    async def Heartbeat(self, request: HeartbeatRequest, context) -> HeartbeatResponse:
        """Handle heartbeat to maintain connection with enhanced status"""
        try:
            self.heartbeat_counter += 1
            current_time = int(time.time() * 1000)

            # Check if we're fully initialized
            is_ready = getattr(self.health_service, 'initialization_complete', False)
            
            # Log periodic heartbeats with status
            if self.heartbeat_counter % 10 == 0:
                status = "RUNNING" if is_ready else "SPINNING"
                uptime = time.time() - self.startup_time
                logger.debug(f"Heartbeat #{self.heartbeat_counter} - Status: {status} - Uptime: {uptime:.1f}s")

            return HeartbeatResponse(
                success=True,
                server_timestamp=current_time
            )
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return HeartbeatResponse(success=False)

    def log_status_transition(component: str, old_status: str, new_status: str, details: str = ""):
        """Log status transitions with structured data"""
        logger.info(
            f"Status transition: {component}",
            extra={
                "component": component,
                "old_status": old_status,
                "new_status": new_status,
                "details": details,
                "timestamp": time.time()
            }
        )
        
    # Add this method to the class
    async def start_health_service(self):
        """Start the health check HTTP server"""
        await self.health_service.setup()

    # Add this method as well
    async def stop_health_service(self):
        """Stop the health check HTTP server"""
        await self.health_service.shutdown()

    async def receive_market_data(self, market_data_list):
        """
        Process received market data from distributor
        
        Args:
            market_data_list: List of market data updates
        """
        try:
            # Update the exchange manager with the new market data
            await self.exchange_manager.update_market_data(market_data_list)
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
            logger.info(f"Client {client_id} subscribed to exchange data stream")

            update_count = 0

            # Send initial update immediately if we have data
            symbols = list(self.exchange_manager.current_market_data.keys())
            if symbols:
                # Get the market data
                market_data = []
                for symbol in symbols:
                    market_data.append(self.exchange_manager.current_market_data[symbol])

                # Generate portfolio and orders data
                portfolio_data = {
                    'cash_balance': self.exchange_manager.cash_balance,
                    'total_value': self.exchange_manager._calculate_total_portfolio_value(market_data),
                    'positions': [
                        {
                            'symbol': symbol,
                            'quantity': position['quantity'],
                            'average_cost': position['average_cost'],
                            'market_value': position['quantity'] * self.exchange_manager._get_current_price(symbol,
                                                                                                            market_data)
                        }
                        for symbol, position in self.exchange_manager.positions.items()
                    ]
                }

                # Get order updates
                orders_data = [
                    {
                        'order_id': order_id,
                        'symbol': order['symbol'],
                        'status': order['status'],
                        'filled_quantity': order.get('filled_quantity', 0),
                        'average_price': order.get('average_price', 0)
                    }
                    for order_id, order in self.exchange_manager.orders.items()
                ]

                # Create and send initial update
                update = ExchangeDataUpdate(
                    timestamp=int(time.time() * 1000)
                )

                # Add market data
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

                update_count += 1
                logger.info(f"Sending initial update #{update_count} to client {client_id} for {len(symbols)} symbols")
                yield update

            # Set up a task to listen for updates with a timeout
            while True:
                try:
                    # Wait for notification of new market data (with timeout)
                    # The timeout ensures we still send periodic updates even if no market data arrives
                    await asyncio.wait_for(
                        self.exchange_manager.market_data_updates.get(),
                        timeout=60  # Still maintain a 60-second maximum interval
                    )

                    # Get symbols from the current market data
                    symbols = list(self.exchange_manager.current_market_data.keys())

                    if not symbols:
                        continue

                    # Get the market data
                    market_data = []
                    for symbol in symbols:
                        market_data.append(self.exchange_manager.current_market_data[symbol])

                    # Generate portfolio and orders data
                    portfolio_data = {
                        'cash_balance': self.exchange_manager.cash_balance,
                        'total_value': self.exchange_manager._calculate_total_portfolio_value(market_data),
                        'positions': [
                            {
                                'symbol': symbol,
                                'quantity': position['quantity'],
                                'average_cost': position['average_cost'],
                                'market_value': position['quantity'] * self.exchange_manager._get_current_price(symbol,
                                                                                                                market_data)
                            }
                            for symbol, position in self.exchange_manager.positions.items()
                        ]
                    }

                    # Get order updates
                    orders_data = [
                        {
                            'order_id': order_id,
                            'symbol': order['symbol'],
                            'status': order['status'],
                            'filled_quantity': order.get('filled_quantity', 0),
                            'average_price': order.get('average_price', 0)
                        }
                        for order_id, order in self.exchange_manager.orders.items()
                    ]

                    # Create and send update
                    update = ExchangeDataUpdate(
                        timestamp=int(time.time() * 1000)
                    )

                    # Add market data
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

                    update_count += 1
                    logger.info(f"Sending update #{update_count} to client {client_id} for {len(symbols)} symbols")
                    yield update

                except asyncio.TimeoutError:
                    # Timeout occurred, send an update anyway
                    logger.debug("No market data updates received for 60 seconds, sending periodic update")

                    symbols = list(self.exchange_manager.current_market_data.keys())
                    if not symbols:
                        continue

                    # Get the market data
                    market_data = []
                    for symbol in symbols:
                        market_data.append(self.exchange_manager.current_market_data[symbol])

                    # Generate portfolio and orders data (same as above)
                    portfolio_data = {
                        'cash_balance': self.exchange_manager.cash_balance,
                        'total_value': self.exchange_manager._calculate_total_portfolio_value(market_data),
                        'positions': [
                            {
                                'symbol': symbol,
                                'quantity': position['quantity'],
                                'average_cost': position['average_cost'],
                                'market_value': position['quantity'] * self.exchange_manager._get_current_price(symbol,
                                                                                                                market_data)
                            }
                            for symbol, position in self.exchange_manager.positions.items()
                        ]
                    }

                    # Get order updates
                    orders_data = [
                        {
                            'order_id': order_id,
                            'symbol': order['symbol'],
                            'status': order['status'],
                            'filled_quantity': order.get('filled_quantity', 0),
                            'average_price': order.get('average_price', 0)
                        }
                        for order_id, order in self.exchange_manager.orders.items()
                    ]

                    # Create and send update
                    update = ExchangeDataUpdate(
                        timestamp=int(time.time() * 1000)
                    )

                    # Add market data
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

                    update_count += 1
                    logger.info(
                        f"Sending periodic update #{update_count} to client {client_id} for {len(symbols)} symbols")
                    yield update

        except asyncio.CancelledError:
            logger.info(f"Stream data generation cancelled for client {client_id}")
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

            # Log the batch request
            logger.info(f"Received batch order submission with {len(request.orders)} orders")

            # Process each order in the batch
            for order_request in request.orders:
                # Extract order parameters
                symbol = order_request.symbol
                side = "BUY" if order_request.side == 0 else "SELL"
                quantity = order_request.quantity
                price = order_request.price if order_request.type == 1 else None  # Only for LIMIT
                order_type = "MARKET" if order_request.type == 0 else "LIMIT"
                request_id = order_request.request_id

                # Generate a unique order ID
                order_id = str(uuid.uuid4())

                # Create a successful result for this order (just logging, not actually processing)
                result = OrderResponse(
                    success=True,
                    order_id=order_id
                )

                logger.info(f"Processed order: {symbol} {side} {quantity} {order_type} -> {order_id}")

                # Add the result to our batch response
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

            # Log the batch cancellation request
            logger.info(f"Received batch order cancellation for {len(request.order_ids)} orders")

            # Process each order ID in the batch
            for order_id in request.order_ids:
                # Just log the cancellation, not actually processing
                logger.info(f"Cancelling order: {order_id}")

                # Create result for this cancellation
                result = CancelResult(
                    order_id=order_id,
                    success=True
                )

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
