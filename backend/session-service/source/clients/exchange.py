# backend/session-service/source/clients/exchange.py
"""
Exchange service gRPC client.
Handles communication with the exchange simulator service using gRPC.
"""
import logging
import asyncio
import time
import json
import grpc
from typing import Any, AsyncGenerator, Dict, Tuple

from source.utils.circuit_breaker import CircuitOpenError
from source.utils.metrics import track_circuit_breaker_failure
from source.utils.tracing import optional_trace_span
from source.clients.base import BaseClient

from source.models.exchange_data import ExchangeType, ExchangeDataUpdate
from source.core.exchange.factory import ExchangeAdapterFactory

from source.api.grpc.session_exchange_interface_pb2 import (
    StreamRequest,
    ExchangeDataUpdate,
    HeartbeatRequest,
    SimulatorStatus,
    ExchangeSimulatorStub
)
from source.api.grpc.session_exchange_interface_pb2_grpc import SessionExchangeSimulatorStub

logger = logging.getLogger('exchange_client')


class ExchangeClient(BaseClient):
    """Client for the exchange simulator gRPC service."""

    def __init__(self):
        """Initialize the exchange client."""
        super().__init__(service_name="exchange_service")
        self.channels = {}
        self.stubs = {}
        self._conn_lock = asyncio.Lock()
        
        # Default gRPC channel options
        self.default_channel_options = [
            ('grpc.keepalive_time_ms', 60000),
            ('grpc.keepalive_timeout_ms', 20000),
            ('grpc.keepalive_permit_without_calls', 1),
            ('grpc.http2.max_pings_without_data', 5),
            ('grpc.http2.min_time_between_pings_ms', 60000),
            ('grpc.http2.min_ping_interval_without_data_ms', 12000)
        ]

        # Default exchange type
        self.default_exchange_type = ExchangeType.EQUITIES

    async def get_channel(self, endpoint: str) -> Tuple[grpc.aio.Channel, ExchangeSimulatorStub]:
        """Get or create gRPC channel for the given endpoint."""
        logger.info(f"DEBUG: get_channel called with endpoint: {endpoint}")
        
        if endpoint in self._channels:
            channel, stub = self._channels[endpoint]
            logger.info(f"DEBUG: Reusing existing channel for {endpoint}")
            
            # CHECK IF CHANNEL IS ACTUALLY HEALTHY
            try:
                # Test the channel state
                state = channel.get_state()
                logger.info(f"DEBUG: Channel state for {endpoint}: {state}")
                
                if state == grpc.ChannelConnectivity.TRANSIENT_FAILURE or state == grpc.ChannelConnectivity.SHUTDOWN:
                    logger.warning(f"DEBUG: Channel {endpoint} is in bad state {state}, recreating...")
                    await channel.close()
                    del self._channels[endpoint]
                else:
                    return channel, stub
                    
            except Exception as e:
                logger.error(f"DEBUG: Error checking channel state for {endpoint}: {e}")
                del self._channels[endpoint]

        logger.info(f"DEBUG: Creating NEW gRPC channel for {endpoint}")
        
        # Force DNS resolution check
        import socket
        try:
            host = endpoint.split(':')[0]
            port = int(endpoint.split(':')[1])
            logger.info(f"DEBUG: Testing DNS resolution for {host}:{port}")
            socket.getaddrinfo(host, port)
            logger.info(f"DEBUG: DNS resolution successful for {host}")
        except Exception as e:
            logger.error(f"DEBUG: DNS resolution failed for {endpoint}: {e}")

        channel = grpc.aio.insecure_channel(endpoint)
        stub = ExchangeSimulatorStub(channel)
        
        self._channels[endpoint] = (channel, stub)
        logger.info(f"DEBUG: Stored new channel for {endpoint} in cache")
        
        return channel, stub

    async def close(self):
        """Close all gRPC channels."""
        async with self._conn_lock:
            logger.info(f"Closing {len(self.channels)} gRPC channels.")
            
            # Create tasks for closing all channels
            close_tasks = []
            for endpoint, channel in self.channels.items():
                try:
                    close_tasks.append(channel.close())
                except Exception as e:
                    logger.error(f"Error creating close task for {endpoint}: {e}")
            
            # Wait for all channels to close
            if close_tasks:
                await asyncio.gather(*close_tasks, return_exceptions=True)
            
            # Clear dictionaries
            self.channels.clear()
            self.stubs.clear()
            logger.info("Finished closing gRPC channels.")

    async def send_heartbeat(self, endpoint: str, session_id: str, client_id: str) -> Dict[str, Any]:
        """
        Send heartbeat to the simulator and get detailed status.
        
        Args:
            endpoint: The endpoint of the simulator
            session_id: The session ID
            client_id: The client ID
            
        Returns:
            Dict with heartbeat results including status
        """
        with optional_trace_span(self.tracer, "heartbeat_rpc") as span:
            span.set_attribute("rpc.service", "ExchangeSimulator")
            span.set_attribute("rpc.method", "Heartbeat")
            span.set_attribute("net.peer.name", endpoint)
            span.set_attribute("app.session_id", session_id)
            try:
                # Execute request with circuit breaker
                response = await self.execute_with_cb(
                    self._heartbeat_request, endpoint, session_id, client_id
                )
                span.set_attribute("app.success", response.get('success', False))
                span.set_attribute("app.simulator_status", response.get('status', 'UNKNOWN'))
                return response
            except CircuitOpenError:
                logger.debug(f"Circuit open for exchange service (heartbeat)")
                span.set_attribute("error.message", "Exchange service unavailable (Circuit Open)")
                span.set_attribute("app.circuit_open", True)
                return {'success': False, 'error': 'Exchange service unavailable', 'status': 'UNKNOWN'}
            except Exception as e:
                logger.warning(f"Error sending heartbeat via gRPC: {e}")
                span.record_exception(e)
                span.set_attribute("error.message", str(e))
                return {'success': False, 'error': str(e), 'status': 'ERROR'}

    async def stream_exchange_data(
            self,
            endpoint: str,
            session_id: str,
            client_id: str,
            exchange_type: ExchangeType = None,
    ) -> AsyncGenerator[ExchangeDataUpdate, None]:
        """
        Stream exchange data (market, portfolio, orders) with adapter conversion
        
        Args:
            endpoint: The endpoint of the simulator
            session_id: The session ID
            client_id: The client ID
            exchange_type: Type of exchange to use adapter for
            
        Yields:
            Standardized ExchangeDataUpdate objects
        """
        with optional_trace_span(self.tracer, "stream_exchange_data_rpc") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("client_id", client_id)
            span.set_attribute("endpoint", endpoint)
            
            # Use the specified exchange type or default
            exchange_type = exchange_type or self.default_exchange_type
            span.set_attribute("exchange_type", exchange_type.value)
            
            # Get the appropriate adapter
            adapter = ExchangeAdapterFactory.get_adapter(exchange_type)

            try:
                # Get channel and stub
                channel, stub = await self.get_channel(endpoint)
                
                # Create stream request
                request = StreamRequest(
                    client_id=client_id,
                )

                # Initiate streaming RPC
                try:
                    stream = stub.StreamExchangeData(request, wait_for_ready=True)
                    logger.info("Initiated StreamExchangeData RPC")
                except Exception as rpc_init_error:
                    logger.error(f"Failed to initiate streaming RPC: {rpc_init_error}")
                    span.record_exception(rpc_init_error)
                    raise

                # Stream processing with direct adapter conversion
                try:
                    async for data in stream:
                        logger.debug(f"Received raw exchange data update")
                        
                        # Direct conversion in one step
                        standardized_data = await adapter.convert_from_protobuf(data)
                        
                        # Set exchange type explicitly if needed
                        standardized_data.exchange_type = exchange_type
                        
                        # Yield the standardized data
                        yield standardized_data
                        
                except Exception as stream_error:
                    logger.error(f"Error in stream processing: {stream_error}")
                    span.record_exception(stream_error)
                    raise

            except Exception as e:
                logger.error(f"Exchange data stream error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                raise

    async def _close_endpoint_channel(self, endpoint: str):
        """
        Close a specific endpoint channel.

        Args:
            endpoint: The endpoint to close the channel for
        """
        if endpoint in self.channels:
            try:
                await self.channels[endpoint].close()
                logger.debug(f"Closed channel to {endpoint}")
            except Exception as e:
                logger.error(f"Error closing channel to {endpoint}: {e}")

            # Remove from dicts regardless of close success
            del self.channels[endpoint]
            del self.stubs[endpoint]

    async def _heartbeat_request(self, endpoint: str, session_id: str, client_id: str) -> Dict[str, Any]:
        """Make the actual heartbeat request."""
        logger.info(f"DEBUG: About to send heartbeat to {endpoint} for session {session_id}")
        
        _, stub = await self.get_channel(endpoint)

        request = HeartbeatRequest(
            client_timestamp=int(time.time() * 1000)
        )

        try:
            logger.info(f"DEBUG: Actually calling stub.Heartbeat for {endpoint}")
            response = await stub.Heartbeat(
                request,
                timeout=10,  # Reduced timeout
                wait_for_ready=True
            )

            # Convert status enum to string
            status_str = SimulatorStatus.Name(response.status) if response.status else 'UNKNOWN'

            logger.info(
                f"DEBUG: Got heartbeat response from {endpoint}: success={response.success}, "
                f"timestamp={response.server_timestamp}, status={status_str}"
            )

            return {
                'success': response.success,
                'server_timestamp': response.server_timestamp,
                'status': status_str
            }
        except grpc.aio.AioRpcError as e:
            logger.error(f"DEBUG: gRPC error sending heartbeat to {endpoint} ({e.code()}): {e.details()}")
            raise
        