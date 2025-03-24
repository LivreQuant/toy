"""
Exchange service gRPC client.
Handles communication with the exchange simulator service using gRPC.
"""
import logging
import asyncio
import time
import grpc
from typing import Dict, List, Any, Optional, AsyncGenerator

from source.utils.circuit_breaker import CircuitBreaker, CircuitOpenError
from source.config import config

# These would be generated from your proto files
import exchange_simulator_pb2
import exchange_simulator_pb2_grpc

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
            stub = exchange_simulator_pb2_grpc.ExchangeSimulatorStub(channel)
            
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
        try:
            # Execute request with circuit breaker
            return await self.circuit_breaker.execute(
                self._start_simulator_request, 
                endpoint, session_id, user_id, initial_symbols, initial_cash
            )
        except CircuitOpenError as e:
            logger.warning(f"Circuit open for exchange service: {e}")
            return {'success': False, 'error': 'Exchange service unavailable'}
        except Exception as e:
            logger.error(f"Error starting simulator: {e}")
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
        
        request = exchange_simulator_pb2.StartSimulatorRequest(
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
        
        request = exchange_simulator_pb2.StopSimulatorRequest(
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
        
        request = exchange_simulator_pb2.HeartbeatRequest(
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
            logger.error(f"gRPC error sending heartbe