import logging
import time
import grpc
import asyncio
from typing import Dict, Any, List, Optional, AsyncIterable

from source.core.exchange_simulator import ExchangeSimulator
from source.utils.metrics import Metrics, timed

# Import generated proto files
import exchange_simulator_pb2
import exchange_simulator_pb2_grpc

logger = logging.getLogger(__name__)
metrics = Metrics()

class ExchangeSimulatorService(exchange_simulator_pb2_grpc.ExchangeSimulatorServicer):
    """gRPC service implementation for exchange simulator"""
    
    def __init__(self, simulator: ExchangeSimulator):
        """
        Initialize service with simulator
        
        Args:
            simulator: Exchange simulator instance
        """
        self.simulator = simulator

    @timed("grpc_start_simulator")
    async def StartSimulator(self, request, context):
        """
        Start a simulator for a specific session
        
        Args:
            request: StartSimulatorRequest
            context: gRPC context
            
        Returns:
            StartSimulatorResponse
        """
        metrics.increment_counter("grpc_start_simulator_called")
        
        # Extract parameters
        session_id = request.session_id
        user_id = request.user_id
        initial_symbols = list(request.initial_symbols) if request.initial_symbols else None
        initial_cash = request.initial_cash if request.initial_cash > 0 else None
        
        logger.info(f"StartSimulator request for session {session_id}, user {user_id}")
        
        # Validate parameters
        if not session_id or not user_id:
            error_msg = "Missing required parameters: session_id and user_id"
            logger.warning(f"StartSimulator failed: {error_msg}")
            return exchange_simulator_pb2.StartSimulatorResponse(
                success=False,
                error_message=error_msg
            )
        
        # Start simulator
        success, simulator_id, error = self.simulator.start_session(
            session_id, user_id, initial_symbols, initial_cash
        )
        
        if not success:
            logger.warning(f"StartSimulator failed: {error}")
            metrics.increment_counter("grpc_start_simulator_failed")
            
        return exchange_simulator_pb2.StartSimulatorResponse(
            success=success,
            simulator_id=simulator_id,
            error_message=error
        )

    @timed("grpc_stop_simulator")
    async def StopSimulator(self, request, context):
        """
        Stop a simulator
        
        Args:
            request: StopSimulatorRequest
            context: gRPC context
            
        Returns:
            StopSimulatorResponse
        """
        metrics.increment_counter("grpc_stop_simulator_called")
        
        # Extract parameters
        session_id = request.session_id
        
        logger.info(f"StopSimulator request for session {session_id}")
        
        # Validate parameters
        if not session_id:
            error_msg = "Missing required parameter: session_id"
            logger.warning(f"StopSimulator failed: {error_msg}")
            return exchange_simulator_pb2.StopSimulatorResponse(
                success=False,
                error_message=error_msg
            )
        
        # Stop simulator
        success, error = self.simulator.stop_session(session_id)
        
        if not success:
            logger.warning(f"StopSimulator failed: {error}")
            metrics.increment_counter("grpc_stop_simulator_failed")
            
        return exchange_simulator_pb2.StopSimulatorResponse(
            success=success,
            error_message=error
        )

    @timed("grpc_stream_exchange_data")
    async def StreamExchangeData(self, request, context):
        """
        Stream exchange data updates
        
        Args:
            request: StreamRequest
            context: gRPC context
            
        Returns:
            AsyncIterable of ExchangeDataUpdate
        """
        metrics.increment_counter("grpc_stream_exchange_data_called")
        
        # Extract parameters
        session_id = request.session_id
        client_id = request.client_id
        symbols = list(request.symbols) if request.symbols else None
        
        logger.info(f"StreamExchangeData request for session {session_id}, client {client_id}")
        
        # Validate parameters
        if not session_id:
            logger.warning("StreamExchangeData failed: Missing session_id")
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Missing required parameter: session_id")
            return
        
        # Check if session exists
        if not self.simulator.update_session_activity(session_id):
            logger.warning(f"StreamExchangeData failed: Session {session_id} not found")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Session {session_id} not found")
            return
        
        # Register stream
        if not self.simulator.register_stream(session_id, client_id, context):
            logger.warning(f"StreamExchangeData failed: Cannot register stream for session {session_id}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Cannot register stream for session {session_id}")
            return
        
        try:
            # Keep stream open until client disconnects or context is cancelled
            update_interval = 1.0  # seconds
            
            while True:
                # Check if context is still active
                if context.cancelled():
                    logger.info(f"StreamExchangeData: Context cancelled for session {session_id}")
                    break
                
                # Create update data
                portfolio = self.simulator.portfolio_manager.get_portfolio(session_id)
                if not portfolio:
                    logger.warning(f"StreamExchangeData: Portfolio not found for session {session_id}")
                    break
                
                # Get market data for requested symbols or portfolio positions
                if symbols:
                    market_data = self.simulator.market_data.get_market_data(symbols)
                else:
                    # Default to portfolio symbols
                    portfolio_symbols = list(portfolio.positions.keys())
                    market_data = self.simulator.market_data.get_market_data(portfolio_symbols)
                
                # Get recent orders
                recent_orders = self.simulator.order_manager.get_recent_orders(session_id)
                
                # Create protobuf response
                response = exchange_simulator_pb2.ExchangeDataUpdate(
                    timestamp=int(time.time() * 1000)
                )
                
                # Add market data
                for item in market_data:
                    response.market_data.append(exchange_simulator_pb2.MarketData(
                        symbol=item['symbol'],
                        bid=item['bid'],
                        ask=item['ask'],
                        bid_size=item['bid_size'],
                        ask_size=item['ask_size'],
                        last_price=item['last_price'],
                        last_size=item['last_size']
                    ))
                
                # Add order updates
                for order in recent_orders:
                    response.order_updates.append(exchange_simulator_pb2.OrderUpdate(
                        order_id=order['order_id'],
                        symbol=order['symbol'],
                        status=order['status'],
                        filled_quantity=order['filled_quantity'],
                        average_price=order['average_price']
                    ))
                
                # Add portfolio
                portfolio_data = portfolio.to_proto_format()
                portfolio_proto = exchange_simulator_pb2.PortfolioStatus(
                    cash_balance=portfolio_data['cash_balance'],
                    total_value=portfolio_data['total_value']
                )
                
                # Add positions
                for pos in portfolio_data['positions']:
                    portfolio_proto.positions.append(exchange_simulator_pb2.Position(
                        symbol=pos['symbol'],
                        quantity=int(pos['quantity']),
                        average_cost=pos['average_cost'],
                        market_value=pos['market_value']
                    ))
                
                response.portfolio.CopyFrom(portfolio_proto)
                
                # Send update
                yield response
                metrics.increment_counter("grpc_stream_data_sent")
                
                # Wait before next update
                await asyncio.sleep(update_interval)
                
        except asyncio.CancelledError:
            logger.info(f"StreamExchangeData cancelled for session {session_id}")
        except Exception as e:
            logger.error(f"Error in StreamExchangeData for session {session_id}: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Stream error: {str(e)}")
        finally:
            # Unregister stream
            self.simulator.unregister_stream(session_id, context)
            logger.info(f"StreamExchangeData ended for session {session_id}")

    @timed("grpc_heartbeat")
    async def Heartbeat(self, request, context):
        """
        Process heartbeat to keep connection alive
        
        Args:
            request: HeartbeatRequest
            context: gRPC context
            
        Returns:
            HeartbeatResponse
        """
        # Extract parameters
        session_id = request.session_id
        client_id = request.client_id
        client_timestamp = request.client_timestamp
        
        # Update session activity
        if session_id:
            self.simulator.update_session_activity(session_id)
        
        # Calculate latency if client timestamp provided
        server_timestamp = int(time.time() * 1000)
        latency = None
        
        if client_timestamp > 0:
            latency = server_timestamp - client_timestamp
            if latency > 0:
                metrics.observe_histogram("heartbeat_latency_ms", latency)
        
        return exchange_simulator_pb2.HeartbeatResponse(
            success=True,
            server_timestamp=server_timestamp
        )

    @timed("grpc_submit_order")
    async def SubmitOrder(self, request, context):
        """
        Submit an order
        
        Args:
            request: SubmitOrderRequest
            context: gRPC context
            
        Returns:
            SubmitOrderResponse
        """
        metrics.increment_counter("grpc_submit_order_called")
        
        # Extract parameters
        session_id = request.session_id
        symbol = request.symbol
        side = "BUY" if request.side == 0 else "SELL"
        quantity = float(request.quantity)
        price = float(request.price) if request.price > 0 else None
        order_type = "MARKET" if request.type == 0 else "LIMIT"
        request_id = request.request_id
        
        logger.info(f"SubmitOrder request for session {session_id}: {quantity} {symbol} {side}")
        
        # Validate session
        if not self.simulator.update_session_activity(session_id):
            logger.warning(f"SubmitOrder failed: Session {session_id} not found")
            return exchange_simulator_pb2.SubmitOrderResponse(
                success=False,
                error_message="Session not found or not active"
            )
        
        # Submit order
        result = self.simulator.order_manager.submit_order(
            session_id, symbol, side, quantity, price, order_type, request_id
        )
        
        if not result.get('success'):
            logger.warning(f"SubmitOrder failed: {result.get('error_message')}")
            metrics.increment_counter("grpc_submit_order_failed")
        else:
            metrics.increment_counter("grpc_submit_order_success")
        
        return exchange_simulator_pb2.SubmitOrderResponse(
            success=result.get('success', False),
            order_id=result.get('order_id', ''),
            error_message=result.get('error_message', '')
        )

    @timed("grpc_cancel_order")
    async def CancelOrder(self, request, context):
        """
        Cancel an order
        
        Args:
            request: CancelOrderRequest
            context: gRPC context
            
        Returns:
            CancelOrderResponse
        """
        metrics.increment_counter("grpc_cancel_order_called")
        
        # Extract parameters
        session_id = request.session_id
        order_id = request.order_id
        
        logger.info(f"CancelOrder request for session {session_id}, order {order_id}")
        
        # Validate session
        if not self.simulator.update_session_activity(session_id):
            logger.warning(f"CancelOrder failed: Session {session_id} not found")
            return exchange_simulator_pb2.CancelOrderResponse(
                success=False,
                error_message="Session not found or not active"
            )
        
        # Cancel order
        result = self.simulator.order_manager.cancel_order(session_id, order_id)
        
        if not result.get('success'):
            logger.warning(f"CancelOrder failed: {result.get('error_message')}")
            metrics.increment_counter("grpc_cancel_order_failed")
        else:
            metrics.increment_counter("grpc_cancel_order_success")
        
        return exchange_simulator_pb2.CancelOrderResponse(
            success=result.get('success', False),
            error_message=result.get('error_message', '')
        )

    import logging
import time
import grpc
import asyncio
from typing import Dict, Any, List, Optional, AsyncIterable

from source.core.exchange_simulator import ExchangeSimulator
from source.utils.metrics import Metrics, timed

# Import generated proto files
import exchange_simulator_pb2
import exchange_simulator_pb2_grpc

logger = logging.getLogger(__name__)
metrics = Metrics()

class ExchangeSimulatorService(exchange_simulator_pb2_grpc.ExchangeSimulatorServicer):
    """gRPC service implementation for exchange simulator"""
    
    def __init__(self, simulator: ExchangeSimulator):
        """
        Initialize service with simulator
        
        Args:
            simulator: Exchange simulator instance
        """
        self.simulator = simulator

    @timed("grpc_start_simulator")
    async def StartSimulator(self, request, context):
        """
        Start a simulator for a specific session
        
        Args:
            request: StartSimulatorRequest
            context: gRPC context
            
        Returns:
            StartSimulatorResponse
        """
        metrics.increment_counter("grpc_start_simulator_called")
        
        # Extract parameters
        session_id = request.session_id
        user_id = request.user_id
        initial_symbols = list(request.initial_symbols) if request.initial_symbols else None
        initial_cash = request.initial_cash if request.initial_cash > 0 else None
        
        logger.info(f"StartSimulator request for session {session_id}, user {user_id}")
        
        # Validate parameters
        if not session_id or not user_id:
            error_msg = "Missing required parameters: session_id and user_id"
            logger.warning(f"StartSimulator failed: {error_msg}")
            return exchange_simulator_pb2.StartSimulatorResponse(
                success=False,
                error_message=error_msg
            )
        
        # Start simulator
        success, simulator_id, error = self.simulator.start_session(
            session_id, user_id, initial_symbols, initial_cash
        )
        
        if not success:
            logger.warning(f"StartSimulator failed: {error}")
            metrics.increment_counter("grpc_start_simulator_failed")
            
        return exchange_simulator_pb2.StartSimulatorResponse(
            success=success,
            simulator_id=simulator_id,
            error_message=error
        )

    @timed("grpc_stop_simulator")
    async def StopSimulator(self, request, context):
        """
        Stop a simulator
        
        Args:
            request: StopSimulatorRequest
            context: gRPC context
            
        Returns:
            StopSimulatorResponse
        """
        metrics.increment_counter("grpc_stop_simulator_called")
        
        # Extract parameters
        session_id = request.session_id
        
        logger.info(f"StopSimulator request for session {session_id}")
        
        # Validate parameters
        if not session_id:
            error_msg = "Missing required parameter: session_id"
            logger.warning(f"StopSimulator failed: {error_msg}")
            return exchange_simulator_pb2.StopSimulatorResponse(
                success=False,
                error_message=error_msg
            )
        
        # Stop simulator
        success, error = self.simulator.stop_session(session_id)
        
        if not success:
            logger.warning(f"StopSimulator failed: {error}")
            metrics.increment_counter("grpc_stop_simulator_failed")
            
        return exchange_simulator_pb2.StopSimulatorResponse(
            success=success,
            error_message=error
        )

    @timed("grpc_stream_exchange_data")
    async def StreamExchangeData(self, request, context):
        """
        Stream exchange data updates
        
        Args:
            request: StreamRequest
            context: gRPC context
            
        Returns:
            AsyncIterable of ExchangeDataUpdate
        """
        metrics.increment_counter("grpc_stream_exchange_data_called")
        
        # Extract parameters
        session_id = request.session_id
        client_id = request.client_id
        symbols = list(request.symbols) if request.symbols else None
        
        logger.info(f"StreamExchangeData request for session {session_id}, client {client_id}")
        
        # Validate parameters
        if not session_id:
            logger.warning("StreamExchangeData failed: Missing session_id")
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Missing required parameter: session_id")
            return
        
        # Check if session exists
        if not self.simulator.update_session_activity(session_id):
            logger.warning(f"StreamExchangeData failed: Session {session_id} not found")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Session {session_id} not found")
            return
        
        # Register stream
        if not self.simulator.register_stream(session_id, client_id, context):
            logger.warning(f"StreamExchangeData failed: Cannot register stream for session {session_id}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Cannot register stream for session {session_id}")
            return
        
        try:
            # Keep stream open until client disconnects or context is cancelled
            update_interval = 1.0  # seconds
            
            while True:
                # Check if context is still active
                if context.cancelled():
                    logger.info(f"StreamExchangeData: Context cancelled for session {session_id}")
                    break
                
                # Create update data
                portfolio = self.simulator.portfolio_manager.get_portfolio(session_id)
                if not portfolio:
                    logger.warning(f"StreamExchangeData: Portfolio not found for session {session_id}")
                    break
                
                # Get market data for requested symbols or portfolio positions
                if symbols:
                    market_data = self.simulator.market_data.get_market_data(symbols)
                else:
                    # Default to portfolio symbols
                    portfolio_symbols = list(portfolio.positions.keys())
                    market_data = self.simulator.market_data.get_market_data(portfolio_symbols)
                
                # Get recent orders
                recent_orders = self.simulator.order_manager.get_recent_orders(session_id)
                
                # Create protobuf response
                response = exchange_simulator_pb2.ExchangeDataUpdate(
                    timestamp=int(time.time() * 1000)
                )
                
                # Add market data
                for item in market_data:
                    response.market_data.append(exchange_simulator_pb2.MarketData(
                        symbol=item['symbol'],
                        bid=item['bid'],
                        ask=item['ask'],
                        bid_size=item['bid_size'],
                        ask_size=item['ask_size'],
                        last_price=item['last_price'],
                        last_size=item['last_size']
                    ))
                
                # Add order updates
                for order in recent_orders:
                    response.order_updates.append(exchange_simulator_pb2.OrderUpdate(
                        order_id=order['order_id'],
                        symbol=order['symbol'],
                        status=order['status'],
                        filled_quantity=order['filled_quantity'],
                        average_price=order['average_price']
                    ))
                
                # Add portfolio
                portfolio_data = portfolio.to_proto_format()
                portfolio_proto = exchange_simulator_pb2.PortfolioStatus(
                    cash_balance=portfolio_data['cash_balance'],
                    total_value=portfolio_data['total_value']
                )
                
                # Add positions
                for pos in portfolio_data['positions']:
                    portfolio_proto.positions.append(exchange_simulator_pb2.Position(
                        symbol=pos['symbol'],
                        quantity=int(pos['quantity']),
                        average_cost=pos['average_cost'],
                        market_value=pos['market_value']
                    ))
                
                response.portfolio.CopyFrom(portfolio_proto)
                
                # Send update
                yield response
                metrics.increment_counter("grpc_stream_data_sent")
                
                # Wait before next update
                await asyncio.sleep(update_interval)
                
        except asyncio.CancelledError:
            logger.info(f"StreamExchangeData cancelled for session {session_id}")
        except Exception as e:
            logger.error(f"Error in StreamExchangeData for session {session_id}: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Stream error: {str(e)}")
        finally:
            # Unregister stream
            self.simulator.unregister_stream(session_id, context)
            logger.info(f"StreamExchangeData ended for session {session_id}")

    @timed("grpc_heartbeat")
    async def Heartbeat(self, request, context):
        """
        Process heartbeat to keep connection alive
        
        Args:
            request: HeartbeatRequest
            context: gRPC context
            
        Returns:
            HeartbeatResponse
        """
        # Extract parameters
        session_id = request.session_id
        client_id = request.client_id
        client_timestamp = request.client_timestamp
        
        # Update session activity
        if session_id:
            self.simulator.update_session_activity(session_id)
        
        # Calculate latency if client timestamp provided
        server_timestamp = int(time.time() * 1000)
        latency = None
        
        if client_timestamp > 0:
            latency = server_timestamp - client_timestamp
            if latency > 0:
                metrics.observe_histogram("heartbeat_latency_ms", latency)
        
        return exchange_simulator_pb2.HeartbeatResponse(
            success=True,
            server_timestamp=server_timestamp
        )

    @timed("grpc_submit_order")
    async def SubmitOrder(self, request, context):
        """
        Submit an order
        
        Args:
            request: SubmitOrderRequest
            context: gRPC context
            
        Returns:
            SubmitOrderResponse
        """
        metrics.increment_counter("grpc_submit_order_called")
        
        # Extract parameters
        session_id = request.session_id
        symbol = request.symbol
        side = "BUY" if request.side == 0 else "SELL"
        quantity = float(request.quantity)
        price = float(request.price) if request.price > 0 else None
        order_type = "MARKET" if request.type == 0 else "LIMIT"
        request_id = request.request_id
        
        logger.info(f"SubmitOrder request for session {session_id}: {quantity} {symbol} {side}")
        
        # Validate session
        if not self.simulator.update_session_activity(session_id):
            logger.warning(f"SubmitOrder failed: Session {session_id} not found")
            return exchange_simulator_pb2.SubmitOrderResponse(
                success=False,
                error_message="Session not found or not active"
            )
        
        # Submit order
        result = self.simulator.order_manager.submit_order(
            session_id, symbol, side, quantity, price, order_type, request_id
        )
        
        if not result.get('success'):
            logger.warning(f"SubmitOrder failed: {result.get('error_message')}")
            metrics.increment_counter("grpc_submit_order_failed")
        else:
            metrics.increment_counter("grpc_submit_order_success")
        
        return exchange_simulator_pb2.SubmitOrderResponse(
            success=result.get('success', False),
            order_id=result.get('order_id', ''),
            error_message=result.get('error_message', '')
        )

    @timed("grpc_cancel_order")
    async def CancelOrder(self, request, context):
        """
        Cancel an order
        
        Args:
            request: CancelOrderRequest
            context: gRPC context
            
        Returns:
            CancelOrderResponse
        """
        metrics.increment_counter("grpc_cancel_order_called")
        
        # Extract parameters
        session_id = request.session_id
        order_id = request.order_id
        
        logger.info(f"CancelOrder request for session {session_id}, order {order_id}")
        
        # Validate session
        if not self.simulator.update_session_activity(session_id):
            logger.warning(f"CancelOrder failed: Session {session_id} not found")
            return exchange_simulator_pb2.CancelOrderResponse(
                success=False,
                error_message="Session not found or not active"
            )
        
        # Cancel order
        result = self.simulator.order_manager.cancel_order(session_id, order_id)
        
        if not result.get('success'):
            logger.warning(f"CancelOrder failed: {result.get('error_message')}")
            metrics.increment_counter("grpc_cancel_order_failed")
        else:
            metrics.increment_counter("grpc_cancel_order_success")
        
        return exchange_simulator_pb2.CancelOrderResponse(
            success=result.get('success', False),
            error_message=result.get('error_message', '')
        )

    @timed("grpc_get_order_status")
    async def GetOrderStatus(self, request, context):
        """
        Get order status
        
        Args:
            request: GetOrderStatusRequest
            context: gRPC context
            
        Returns:
            GetOrderStatusResponse
        """
        metrics.increment_counter("grpc_get_order_status_called")
        
        # Extract parameters
        session_id = request.session_i