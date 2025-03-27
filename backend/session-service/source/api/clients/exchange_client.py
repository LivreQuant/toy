"""
Exchange service gRPC client.
Handles communication with the exchange simulator service using gRPC.
"""
import logging
import asyncio
import time
import grpc
from typing import Dict, List, Any, Optional, AsyncGenerator
from opentelemetry import trace

from source.utils.circuit_breaker import CircuitBreaker, CircuitOpenError
from source.config import config

from source.utils.metrics import track_external_request, track_circuit_breaker_state, track_circuit_breaker_failure
from source.utils.tracing import optional_trace_span

# These would be generated from your proto files
from source.api.grpc.exchange_simulator_pb2 import (
    StartSimulatorRequest,
    StopSimulatorRequest,
    StreamRequest,
    HeartbeatRequest,
    GetSimulatorStatusRequest
)
from source.api.grpc.exchange_simulator_pb2_grpc import ExchangeSimulatorStub

logger = logging.getLogger('exchange_client')

class ExchangeClient:
    """Client for the exchange simulator gRPC service"""
    
    def __init__(self):
        """Initialize the exchange client"""
        self.channels = {}  # endpoint -> channel
        self.stubs = {}     # endpoint -> stub
        self._conn_lock = asyncio.Lock()
        
        # Create circuit breaker
        self.circuit_breaker = CircuitBreaker(
            name="exchange_service",
            failure_threshold=3,
            reset_timeout_ms=30000  # 30 seconds
        )

        # Register callback for circuit breaker state changes
        self.circuit_breaker.on_state_change(self._on_circuit_state_change)

        # Create tracer
        self.tracer = trace.get_tracer("exchange_client")

    def _on_circuit_state_change(self, name, old_state, new_state, info):
        """Handle circuit breaker state changes"""
        logger.info(f"Circuit breaker '{name}' state change: {old_state.value} -> {new_state.value}")
        track_circuit_breaker_state("exchange_service", new_state.value)

    async def get_channel(self, endpoint: str):
        """Get or create a gRPC channel to the endpoint"""
        async with self._conn_lock:
            if endpoint in self.channels:
                return self.channels[endpoint], self.stubs[endpoint]
            
            # Create channel options
            options = [
                ('grpc.keepalive_time_ms', 10000),        # 10 seconds
                ('grpc.keepalive_timeout_ms', 5000),      # 5 seconds
                ('grpc.keepalive_permit_without_calls', 1),
                ('grpc.http2.max_pings_without_data', 0), 
                ('grpc.http2.min_time_between_pings_ms', 10000),
                ('grpc.http2.min_ping_interval_without_data_ms', 5000)
            ]
            
            # Create channel
            channel = grpc.aio.insecure_channel(endpoint, options=options)
            stub = ExchangeSimulatorStub(channel)
            
            # Store for reuse
            self.channels[endpoint] = channel
            self.stubs[endpoint] = stub
            
            return channel, stub
    
    async def close(self):
        """Close all gRPC channels"""
        async with self._conn_lock:
            for endpoint, channel in self.channels.items():
                try:
                    await channel.close()
                except Exception as e:
                    logger.error(f"Error closing channel to {endpoint}: {e}")
            
            self.channels.clear()
            self.stubs.clear()
    
    async def start_simulator(
        self, 
        endpoint: str,
        session_id: str, 
        user_id: str, 
        initial_symbols: List[str] = None, 
        initial_cash: float = 100000.0
    ) -> Dict[str, Any]:
        """
        Start a simulator instance
        
        Args:
            endpoint: The endpoint of the exchange manager service
            session_id: The session ID
            user_id: The user ID
            initial_symbols: Initial symbols to track
            initial_cash: Initial cash amount
            
        Returns:
            Dict with start results
        """
        with optional_trace_span(self.tracer, "start_simulator") as span:
            span.set_attribute("endpoint", endpoint)
            span.set_attribute("session_id", session_id)
            span.set_attribute("user_id", user_id)
            span.set_attribute("initial_symbols_count", len(initial_symbols or []))
            span.set_attribute("initial_cash", initial_cash)

            try:
                # Execute request with circuit breaker
                return await self.circuit_breaker.execute(
                    self._start_simulator_request,
                    endpoint, session_id, user_id, initial_symbols, initial_cash
                )
            except CircuitOpenError as e:
                logger.warning(f"Circuit open for exchange service: {e}")
                span.set_attribute("error", "Exchange service unavailable")
                span.set_attribute("circuit_open", True)
                return {'success': False, 'error': 'Exchange service unavailable'}
            except Exception as e:
                logger.error(f"Error starting simulator: {e}")
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return {'success': False, 'error': str(e)}

    async def _start_simulator_request(
        self, 
        endpoint: str,
        session_id: str, 
        user_id: str, 
        initial_symbols: List[str] = None, 
        initial_cash: float = 100000.0
    ) -> Dict[str, Any]:
        """Make the actual start simulator request"""
        _, stub = await self.get_channel(endpoint)
        
        request = StartSimulatorRequest(
            session_id=session_id,
            user_id=user_id,
            initial_symbols=initial_symbols or [],
            initial_cash=initial_cash
        )
        
        try:
            response = await stub.StartSimulator(request, timeout=10)
            
            return {
                'success': response.success,
                'simulator_id': response.simulator_id,
                'error': response.error_message if not response.success else None
            }
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC error starting simulator: {e.code()} - {e.details()}")
            raise
    
    async def stop_simulator(self, endpoint: str, session_id: str) -> Dict[str, Any]:
        """
        Stop a simulator instance
        
        Args:
            endpoint: The endpoint of the simulator
            session_id: The session ID
            
        Returns:
            Dict with stop results
        """
        try:
            # Execute request with circuit breaker
            return await self.circuit_breaker.execute(
                self._stop_simulator_request, endpoint, session_id
            )
        except CircuitOpenError as e:
            logger.warning(f"Circuit open for exchange service: {e}")
            return {'success': False, 'error': 'Exchange service unavailable'}
        except Exception as e:
            logger.error(f"Error stopping simulator: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _stop_simulator_request(self, endpoint: str, session_id: str) -> Dict[str, Any]:
        """Make the actual stop simulator request"""
        _, stub = await self.get_channel(endpoint)
        
        request = StopSimulatorRequest(
            session_id=session_id
        )
        
        try:
            response = await stub.StopSimulator(request, timeout=10)
            
            return {
                'success': response.success,
                'error': response.error_message if not response.success else None
            }
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC error stopping simulator: {e.code()} - {e.details()}")
            raise
    
    async def heartbeat(self, endpoint: str, session_id: str, client_id: str) -> Dict[str, Any]:
        """
        Send heartbeat to the simulator
        
        Args:
            endpoint: The endpoint of the simulator
            session_id: The session ID
            client_id: The client ID
            
        Returns:
            Dict with heartbeat results
        """
        try:
            # Execute request with circuit breaker
            return await self.circuit_breaker.execute(
                self._heartbeat_request, endpoint, session_id, client_id
            )
        except CircuitOpenError as e:
            logger.warning(f"Circuit open for exchange service: {e}")
            return {'success': False, 'error': 'Exchange service unavailable'}
        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")
            return {'success': False, 'error': str(e)}

    async def _heartbeat_request(self, endpoint: str, session_id: str, client_id: str) -> Dict[str, Any]:
        """Make the actual heartbeat request"""
        _, stub = await self.get_channel(endpoint)

        request = HeartbeatRequest(
            session_id=session_id,
            client_id=client_id,
            client_timestamp=int(time.time() * 1000)
        )

        try:
            response = await stub.Heartbeat(request, timeout=5)

            return {
                'success': response.success,
                'server_timestamp': response.server_timestamp
            }
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC error sending heartbeat: {e.code()} - {e.details()}")
            raise

    async def stream_exchange_data(
            self,
            endpoint: str,
            session_id: str,
            client_id: str,
            symbols: List[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream market data from the exchange simulator

        Args:
            endpoint: The endpoint of the simulator
            session_id: The session ID
            client_id: The client ID
            symbols: Optional list of symbols to stream (passed through from frontend)

        Yields:
            Dict with market data updates
        """
        _, stub = await self.get_channel(endpoint)

        request = StreamRequest(
            session_id=session_id,
            client_id=client_id,
            symbols=symbols or []
        )

        # This streaming endpoint doesn't use circuit breaker to allow long-running streams
        try:
            stream = stub.StreamMarketData(request)

            async for data in stream:
                # Simply forward the data structure received from the exchange
                # Convert protobuf message to dictionary with minimal transformation
                yield self._convert_stream_data(data)

        except grpc.aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.CANCELLED:
                logger.info(f"Stream cancelled for session {session_id}")
            else:
                logger.error(f"gRPC error in market data stream: {e.code()} - {e.details()}")
            raise
        except Exception as e:
            logger.error(f"Error in market data stream: {e}")
            raise

    def _convert_stream_data(self, data):
        """Convert stream data protobuf message to dictionary"""
        # Minimal conversion from protobuf to dict
        result = {
            'timestamp': data.timestamp,
            'market_data': [],
            'portfolio': None
        }

        # Convert market data
        for item in data.market_data:
            result['market_data'].append({
                'symbol': item.symbol,
                'price': item.price,
                'change': item.change,
                'volume': item.volume,
                'timestamp': item.timestamp
            })

        # Convert portfolio if present
        if data.HasField('portfolio'):
            portfolio = data.portfolio
            positions = []

            for pos in portfolio.positions:
                positions.append({
                    'symbol': pos.symbol,
                    'quantity': pos.quantity,
                    'avg_price': pos.avg_price,
                    'current_price': pos.current_price,
                    'market_value': pos.market_value,
                    'profit_loss': pos.profit_loss
                })

            result['portfolio'] = {
                'cash': portfolio.cash,
                'equity': portfolio.equity,
                'buying_power': portfolio.buying_power,
                'positions': positions
            }

        return result

    async def get_simulator_status(
            self,
            endpoint: str,
            session_id: str
    ) -> Dict[str, Any]:
        """
        Get the status of a simulator instance (for connection management)

        Args:
            endpoint: The endpoint of the simulator
            session_id: The session ID

        Returns:
            Dict with simulator connectivity status
        """
        try:
            # Execute request with circuit breaker
            return await self.circuit_breaker.execute(
                self._get_simulator_status_request, endpoint, session_id
            )
        except CircuitOpenError as e:
            logger.warning(f"Circuit open for exchange service: {e}")
            return {'status': 'UNKNOWN', 'error': 'Exchange service unavailable'}
        except Exception as e:
            logger.error(f"Error getting simulator status: {e}")
            return {'status': 'ERROR', 'error': str(e)}

    async def _get_simulator_status_request(
            self,
            endpoint: str,
            session_id: str
    ) -> Dict[str, Any]:
        """Make the actual simulator status request"""
        _, stub = await self.get_channel(endpoint)

        request = GetSimulatorStatusRequest(
            session_id=session_id
        )

        try:
            response = await stub.GetSimulatorStatus(request, timeout=5)

            return {
                'status': response.status,
                'simulator_id': response.simulator_id,
                'uptime_seconds': response.uptime_seconds,
                'error': response.error_message if response.status == 'ERROR' else None
            }
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC error getting simulator status: {e.code()} - {e.details()}")
            raise