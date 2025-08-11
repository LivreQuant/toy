# source/clients/exchange.py
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
    HeartbeatResponse
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

    async def get_channel(self, endpoint: str) -> Tuple[grpc.aio.Channel, SessionExchangeSimulatorStub]:
        """Get or create gRPC channel for the given endpoint with DNS retry."""
        logger.info(f"DEBUG: get_channel called with endpoint: {endpoint}")
        
        # Add DNS resolution test with retry
        host, port = endpoint.split(':')
        max_dns_retries = 5
        dns_retry_delay = 2
        
        for attempt in range(max_dns_retries):
            try:
                import socket
                socket.getaddrinfo(host, int(port))
                logger.debug(f"DNS resolution successful for {endpoint}")
                break
            except Exception as e:
                if attempt < max_dns_retries - 1:
                    logger.debug(f"DNS resolution failed for {endpoint}, attempt {attempt + 1}: {e}")
                    await asyncio.sleep(dns_retry_delay)
                else:
                    logger.error(f"DNS resolution failed after {max_dns_retries} attempts: {e}")
                    raise
        
        if endpoint in self.channels:
            channel, stub = self.channels[endpoint]
            logger.info(f"DEBUG: Reusing existing channel for {endpoint}")
            
            # CHECK IF CHANNEL IS ACTUALLY HEALTHY
            try:
                # Test the channel state
                state = channel.get_state()
                logger.info(f"DEBUG: Channel state for {endpoint}: {state}")
                
                if state == grpc.ChannelConnectivity.TRANSIENT_FAILURE or state == grpc.ChannelConnectivity.SHUTDOWN:
                    logger.warning(f"DEBUG: Channel {endpoint} is in bad state {state}, recreating...")
                    await channel.close()
                    del self.channels[endpoint]
                else:
                    return channel, stub
                    
            except Exception as e:
                logger.error(f"DEBUG: Error checking channel state for {endpoint}: {e}")
                del self.channels[endpoint]

        logger.info(f"DEBUG: Creating NEW gRPC channel for {endpoint}")

        channel = grpc.aio.insecure_channel(endpoint, options=self.default_channel_options)
        stub = SessionExchangeSimulatorStub(channel)
        
        self.channels[endpoint] = (channel, stub)
        logger.info(f"DEBUG: Stored new channel for {endpoint} in cache")
        
        return channel, stub

    async def close(self):
        """Close all gRPC channels."""
        async with self._conn_lock:
            logger.info(f"Closing {len(self.channels)} gRPC channels.")
            
            # Create tasks for closing all channels
            close_tasks = []
            for endpoint, (channel, stub) in self.channels.items():
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

    async def send_heartbeat(self, endpoint: str, user_id: str, client_id: str) -> Dict[str, Any]:
        """
        Send heartbeat to the simulator and get detailed status.
        TEMPORARILY bypassing circuit breaker for testing.
        """
        with optional_trace_span(self.tracer, "heartbeat_rpc") as span:
            span.set_attribute("rpc.service", "ExchangeSimulator")
            span.set_attribute("rpc.method", "Heartbeat")
            span.set_attribute("net.peer.name", endpoint)
            span.set_attribute("app.user_id", user_id)
            try:
                # BYPASS CIRCUIT BREAKER FOR TESTING - call directly
                logger.info(f"BYPASS: Calling heartbeat directly without circuit breaker")
                response = await self._heartbeat_request(endpoint, user_id, client_id)
                
                span.set_attribute("app.success", response.get('success', False))
                span.set_attribute("app.simulator_status", response.get('status', 'UNKNOWN'))
                logger.info(f"BYPASS: Heartbeat response: {response}")
                return response
            except Exception as e:
                logger.error(f"BYPASS: Error sending heartbeat via gRPC: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error.message", str(e))
                return {'success': False, 'error': str(e), 'status': 'ERROR'}

    async def _heartbeat_request(self, endpoint: str, user_id: str, client_id: str) -> Dict[str, Any]:
        """Make the actual heartbeat request with detailed logging."""
        logger.info(f"DETAILED: About to send heartbeat to {endpoint} for user {user_id}")
        logger.info(f"DETAILED: client_id={client_id}, user_id={user_id}")
        
        _, stub = await self.get_channel(endpoint)

        # Use the correct fields from the protobuf definition
        request = HeartbeatRequest(
            client_id=client_id,
            user_id=user_id,
            session_instance_id=f"session-{user_id}",
            last_received_sequence=0
        )

        logger.info(f"DETAILED: Created HeartbeatRequest:")
        logger.info(f"  - client_id: {request.client_id}")
        logger.info(f"  - user_id: {request.user_id}")
        logger.info(f"  - session_instance_id: {request.session_instance_id}")
        logger.info(f"  - last_received_sequence: {request.last_received_sequence}")

        try:
            logger.info(f"DETAILED: Calling stub.Heartbeat for {endpoint}")
            response = await stub.Heartbeat(
                request,
                timeout=10,
                wait_for_ready=True
            )

            logger.info(f"DETAILED: Got heartbeat response from {endpoint}:")
            logger.info(f"  - status: {response.status}")
            logger.info(f"  - timestamp: {response.timestamp}")
            logger.info(f"  - current_bin: {getattr(response, 'current_bin', 'N/A')}")
            logger.info(f"  - next_bin: {getattr(response, 'next_bin', 'N/A')}")
            logger.info(f"  - market_state: {getattr(response, 'market_state', 'N/A')}")

            # Map the actual protobuf response fields to what the session service expects
            result = {
                'success': True,  # If we got a response, consider it successful
                'server_timestamp': response.timestamp,
                'status': response.status,
                'current_bin': getattr(response, 'current_bin', ''),
                'next_bin': getattr(response, 'next_bin', ''),
                'market_state': getattr(response, 'market_state', '')
            }
            
            logger.info(f"DETAILED: Returning result: {result}")
            return result
            
        except grpc.aio.AioRpcError as e:
            logger.error(f"DETAILED: gRPC error sending heartbeat to {endpoint}")
            logger.error(f"  - Code: {e.code()}")
            logger.error(f"  - Details: {e.details()}")
            logger.error(f"  - Debug info: {e.debug_error_string()}")
            raise
        except Exception as e:
            logger.error(f"DETAILED: Non-gRPC error: {type(e).__name__}: {e}")
            raise
        
    async def stream_exchange_data(
        self,
        endpoint: str,
        session_id: str,
        client_id: str,
        exchange_type: ExchangeType = None,
    ) -> AsyncGenerator[ExchangeDataUpdate, None]:
        """Stream exchange data with better error handling for pod termination"""
        
        with optional_trace_span(self.tracer, "stream_exchange_data_rpc") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("client_id", client_id)
            span.set_attribute("endpoint", endpoint)
            
            exchange_type = exchange_type or self.default_exchange_type
            span.set_attribute("exchange_type", exchange_type.value)
            
            adapter = ExchangeAdapterFactory.get_adapter(exchange_type)

            try:
                channel, stub = await self.get_channel(endpoint)
                
                # Use the correct protobuf fields for StreamRequest
                request = StreamRequest(
                    client_id=client_id,
                    user_id=session_id,  # Use session_id as user_id
                    connection_timestamp=int(time.time() * 1000),
                    session_instance_id=f"session-{session_id}",
                    request_initial_state=True
                )

                try:
                    stream = stub.StreamExchangeData(request, wait_for_ready=True)
                    logger.info("Initiated StreamExchangeData RPC")
                except Exception as rpc_init_error:
                    logger.error(f"Failed to initiate streaming RPC: {rpc_init_error}")
                    span.record_exception(rpc_init_error)
                    raise

                try:
                    async for data in stream:
                        logger.debug(f"Received raw exchange data update")
                        standardized_data = await adapter.convert_from_protobuf(data)
                        standardized_data.exchange_type = exchange_type
                        yield standardized_data
                        
                except Exception as stream_error:
                    # ✅ IMPROVED: Better error categorization
                    error_msg = str(stream_error).lower()
                    is_pod_terminated = any(term in error_msg for term in [
                        'socket closed', 'unavailable', 'connection refused',
                        'name or service not known', 'dns resolution failed'
                    ])
                    
                    if is_pod_terminated:
                        logger.warning(f"Pod terminated for endpoint {endpoint}: {stream_error}")
                    else:
                        logger.error(f"Stream processing error: {stream_error}")
                    
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
                channel, stub = self.channels[endpoint]
                await channel.close()
                logger.debug(f"Closed channel to {endpoint}")
            except Exception as e:
                logger.error(f"Error closing channel to {endpoint}: {e}")

            # Remove from dicts regardless of close success
            del self.channels[endpoint]
            if endpoint in self.stubs:
                del self.stubs[endpoint]