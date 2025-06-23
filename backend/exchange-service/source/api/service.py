# backend/exchange-service/source/api/service.py
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
    PortfolioStatus,
    SimulatorStatus
)
from source.api.grpc.session_exchange_interface_pb2_grpc import SessionExchangeSimulatorServicer

# Import conviction protobuf classes (replacing order classes)
from source.api.grpc.conviction_exchange_interface_pb2 import (
    ConvictionResponse,
    BatchConvictionResponse,
    CancelResult,
    BatchCancelResponse
)
from source.api.grpc.conviction_exchange_interface_pb2_grpc import ConvictionExchangeSimulatorServicer

from source.api.rest.health import HealthService

logger = logging.getLogger('exchange_simulator')


class ExchangeSimulatorService(SessionExchangeSimulatorServicer, ConvictionExchangeSimulatorServicer):
    def __init__(self, exchange_manager: ExchangeManager):
        self.exchange_manager = exchange_manager
        self.last_heartbeat = time.time()
        self.heartbeat_counter = 0
        self.health_service = exchange_manager.get_health_service() if hasattr(exchange_manager, 'get_health_service') else HealthService(exchange_manager, http_port=50056)
        self.startup_time = time.time()
        
        # Internal simulator status tracking
        self.internal_status = SimulatorStatus.INITIALIZING
        self._status_lock = asyncio.Lock()

    async def _update_internal_status(self, new_status: SimulatorStatus):
        """Update the internal simulator status"""
        async with self._status_lock:
            if self.internal_status != new_status:
                old_status = self.internal_status
                self.internal_status = new_status
                logger.info(f"Simulator status changed: {SimulatorStatus.Name(old_status)} -> {SimulatorStatus.Name(new_status)}")

    async def _get_current_status(self) -> SimulatorStatus:
        """Get the current simulator status with logic"""
        async with self._status_lock:
            # Check if we're fully initialized
            is_ready = getattr(self.health_service, 'initialization_complete', False)
            
            if not is_ready:
                return SimulatorStatus.INITIALIZING
            
            # Check if exchange manager is streaming data
            if hasattr(self.exchange_manager, 'current_market_data') and self.exchange_manager.current_market_data:
                # We have market data, so we're running
                if self.internal_status == SimulatorStatus.INITIALIZING:
                    await self._update_internal_status(SimulatorStatus.RUNNING)
                return SimulatorStatus.RUNNING
            
            # Default to current internal status
            return self.internal_status

    async def Heartbeat(self, request: HeartbeatRequest, context) -> HeartbeatResponse:
        """Handle heartbeat to maintain connection with enhanced status"""
        try:
            self.heartbeat_counter += 1
            current_time = int(time.time() * 1000)

            # Get current status
            current_status = await self._get_current_status()
            
            # Log periodic heartbeats with status
            if self.heartbeat_counter % 10 == 0:
                uptime = time.time() - self.startup_time
                logger.info(f"Heartbeat #{self.heartbeat_counter} - Status: {SimulatorStatus.Name(current_status)} - Uptime: {uptime:.1f}s")

            return HeartbeatResponse(
                success=True,
                server_timestamp=current_time,
                status=current_status
            )
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return HeartbeatResponse(
                success=False,
                server_timestamp=int(time.time() * 1000),
                status=SimulatorStatus.ERROR
            )

    async def start_health_service(self):
        """Start the health check HTTP server"""
        await self.health_service.setup()

    async def stop_health_service(self):
        """Stop the health check HTTP server"""
        await self.health_service.shutdown()
        # Update status to stopping
        await self._update_internal_status(SimulatorStatus.STOPPING)

    async def StreamExchangeData(
            self,
            request: StreamRequest,
            context
    ) -> AsyncGenerator[ExchangeDataUpdate, None]:
        """Stream market data, orders, and portfolio updates"""
        try:
            client_id = request.client_id
            logger.info(f"Client {client_id} subscribed to exchange data stream")

            # Mark as running once we start streaming
            await self._update_internal_status(SimulatorStatus.RUNNING)

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
                            'market_value': position['quantity'] * self.exchange_manager._get_current_price(symbol, market_data)
                        }
                        for symbol, position in self.exchange_manager.positions.items()
                    ]
                }

                # Get conviction updates (mapped to orders for compatibility)
                orders_data = [
                    {
                        'order_id': conviction_id,
                        'symbol': conviction['symbol'],
                        'status': conviction['status'],
                        'filled_quantity': conviction.get('filled_quantity', 0),
                        'average_price': conviction.get('average_price', 0)
                    }
                    for conviction_id, conviction in getattr(self.exchange_manager, 'conviction_manager', self.exchange_manager.order_manager).convictions.items() if hasattr(getattr(self.exchange_manager, 'conviction_manager', self.exchange_manager.order_manager), 'convictions')
                ]

                # Fallback to orders if convictions not available
                if not orders_data and hasattr(self.exchange_manager, 'orders'):
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
                    await asyncio.wait_for(
                        self.exchange_manager.market_data_updates.get(),
                        timeout=60
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

                    # Get conviction updates (mapped to orders for compatibility)
                    orders_data = [
                        {
                            'order_id': conviction_id,
                            'symbol': conviction['symbol'],
                            'status': conviction['status'],
                            'filled_quantity': conviction.get('filled_quantity', 0),
                            'average_price': conviction.get('average_price', 0)
                        }
                        for conviction_id, conviction in getattr(self.exchange_manager, 'conviction_manager', self.exchange_manager.order_manager).convictions.items() if hasattr(getattr(self.exchange_manager, 'conviction_manager', self.exchange_manager.order_manager), 'convictions')
                    ]

                    # Fallback to orders if convictions not available
                    if not orders_data and hasattr(self.exchange_manager, 'orders'):
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

                    # Get conviction updates
                    orders_data = [
                        {
                            'order_id': conviction_id,
                            'symbol': conviction['symbol'],
                            'status': conviction['status'],
                            'filled_quantity': conviction.get('filled_quantity', 0),
                            'average_price': conviction.get('average_price', 0)
                        }
                        for conviction_id, conviction in getattr(self.exchange_manager, 'conviction_manager', self.exchange_manager.order_manager).convictions.items() if hasattr(getattr(self.exchange_manager, 'conviction_manager', self.exchange_manager.order_manager), 'convictions')
                    ]

                    # Fallback to orders if convictions not available
                    if not orders_data and hasattr(self.exchange_manager, 'orders'):
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
            await self._update_internal_status(SimulatorStatus.STOPPING)
        except Exception as e:
            logger.error(f"Stream data error: {e}")
            await self._update_internal_status(SimulatorStatus.ERROR)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))

    async def SubmitConvictions(self, request, context):
        """Handle batch conviction submissions"""
        try:
            # Create response object
            response = BatchConvictionResponse(
                success=True,
                results=[]
            )

            # Log the batch request
            logger.info(f"Received batch conviction submission with {len(request.convictions)} convictions")

            # Process each conviction in the batch
            for conviction_request in request.convictions:
                # Extract conviction parameters
                symbol = conviction_request.instrument_id
                side = "BUY" if conviction_request.side == 0 else "SELL"
                quantity = conviction_request.quantity
                conviction_id = conviction_request.conviction_id

                # Generate a unique broker ID
                broker_id = str(uuid.uuid4())

                # Create a successful result for this conviction (just logging, not actually processing)
                result = ConvictionResponse(
                    success=True,
                    broker_id=broker_id
                )

                logger.info(f"Processed conviction: {symbol} {side} {quantity} -> {broker_id}")

                # Add the result to our batch response
                response.results.append(result)

            return response

        except Exception as e:
            logger.error(f"Error processing batch conviction submission: {e}")

            # Return error response
            return BatchConvictionResponse(
                success=False,
                error_message=f"Server error: {str(e)}",
                results=[]
            )

    async def CancelConvictions(self, request, context):
        """Handle batch conviction cancellations"""
        try:
            # Create response object
            response = BatchCancelResponse(
                success=True,
                results=[]
            )

            # Log the batch cancellation request
            logger.info(f"Received batch conviction cancellation for {len(request.conviction_id)} convictions")

            # Process each conviction ID in the batch
            for conviction_id in request.conviction_id:
                # Just log the cancellation, not actually processing
                logger.info(f"Cancelling conviction: {conviction_id}")

                # Create result for this cancellation
                result = CancelResult(
                    broker_id=conviction_id,
                    success=True
                )

                response.results.append(result)

            return response

        except Exception as e:
            logger.error(f"Error processing batch conviction cancellation: {e}")

            # Return error response
            return BatchCancelResponse(
                success=False,
                error_message=f"Server error: {str(e)}",
                results=[]
            )