# source/clients/exchange_client.py
"""
Exchange service gRPC client.
Handles communication with the exchange simulator service using gRPC.
"""
import logging
import asyncio
import time
import json
import grpc
from typing import Any, AsyncGenerator, Dict

from source.utils.circuit_breaker import CircuitOpenError
from source.utils.metrics import track_circuit_breaker_failure
from source.utils.tracing import optional_trace_span
from source.clients.base import BaseClient

from source.api.grpc.exchange_simulator_pb2 import (
    StreamRequest,
    ExchangeDataUpdate,
    HeartbeatRequest,
    HeartbeatResponse,
)
from source.api.grpc.exchange_simulator_pb2_grpc import ExchangeSimulatorStub

logger = logging.getLogger('exchange_client')


def _convert_stream_data(data: ExchangeDataUpdate) -> Dict[str, Any]:
    """Convert ExchangeDataUpdate protobuf message to dictionary."""
    result = {
        'timestamp': data.timestamp,
        'marketData': [],
        'orderUpdates': [],
        'portfolio': None
    }

    # Convert market data
    for item in data.market_data:
        result['marketData'].append({
            'symbol': item.symbol,
            'bid': item.bid,
            'ask': item.ask,
            'bidSize': item.bid_size,
            'askSize': item.ask_size,
            'lastPrice': item.last_price,
            'lastSize': item.last_size
        })

    # Convert order updates
    for item in data.orders_data:
        result['orderUpdates'].append({
            'orderId': item.order_id,
            'symbol': item.symbol,
            'status': item.status,
            'filledQuantity': item.filled_quantity,
            'averagePrice': item.average_price
        })

    # Convert portfolio if present
    if data.HasField('portfolio'):
        portfolio = data.portfolio
        positions_list = []
        for pos in portfolio.positions:
            positions_list.append({
                'symbol': pos.symbol,
                'quantity': pos.quantity,
                'averageCost': pos.average_cost,
                'marketValue': pos.market_value
            })

        result['portfolio'] = {
            'positions': positions_list,
            'cashBalance': portfolio.cash_balance,
            'totalValue': portfolio.total_value
        }

    return result


class ExchangeClient(BaseClient):
    """Client for the exchange simulator gRPC service."""

    def __init__(self):
        """Initialize the exchange client."""
        super().__init__(service_name="exchange_service")
        self.channels: Dict[str, grpc.aio.Channel] = {}
        self.stubs: Dict[str, ExchangeSimulatorStub] = {}
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

    async def get_channel(self, endpoint: str) -> tuple[grpc.aio.Channel, ExchangeSimulatorStub]:
        """
        Get or create a gRPC channel to the endpoint.

        Args:
            endpoint: The simulator endpoint

        Returns:
            Tuple of (channel, stub)
        """
        async with self._conn_lock:
            if endpoint in self.channels:
                try:
                    # Check channel state
                    state = self.channels[endpoint].get_state(try_to_connect=False)
                    # Basic check - if not explicitly shut down, assume OK for now
                    if state != grpc.ChannelConnectivity.SHUTDOWN:
                        return self.channels[endpoint], self.stubs[endpoint]
                except Exception:
                    logger.warning(f"Channel to {endpoint} not usable, recreating")
                    await self._close_endpoint_channel(endpoint)

            # Create new channel if needed
            logger.info(f"Creating new gRPC channel to {endpoint}")

            # Update channel options to include backoff parameters
            options = self.default_channel_options + [
                ('grpc.enable_retries', 1),
                ('grpc.initial_reconnect_backoff_ms', 1000),  # Start with 1 second
                ('grpc.max_reconnect_backoff_ms', 10000),  # Max of 10 seconds
                ('grpc.service_config', json.dumps({
                    'methodConfig': [{
                        'name': [{}],  # Apply to all methods
                        'retryPolicy': {
                            'maxAttempts': 5,
                            'initialBackoff': '1s',
                            'maxBackoff': '10s',
                            'backoffMultiplier': 2.0,
                            'retryableStatusCodes': ['UNAVAILABLE']
                        }
                    }]
                }))
            ]

            # Create channel with enhanced options
            channel = grpc.aio.insecure_channel(endpoint, options=options)
            stub = ExchangeSimulatorStub(channel)

            # Store for reuse
            self.channels[endpoint] = channel
            self.stubs[endpoint] = stub

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
        Send heartbeat to the simulator.
        
        Args:
            endpoint: The endpoint of the simulator
            session_id: The session ID
            client_id: The client ID
            
        Returns:
            Dict with heartbeat results
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
                return response
            except CircuitOpenError:
                logger.debug(f"Circuit open for exchange service (heartbeat)")
                span.set_attribute("error.message", "Exchange service unavailable (Circuit Open)")
                span.set_attribute("app.circuit_open", True)
                return {'success': False, 'error': 'Exchange service unavailable'}
            except Exception as e:
                logger.warning(f"Error sending heartbeat via gRPC: {e}")
                span.record_exception(e)
                span.set_attribute("error.message", str(e))
                return {'success': False, 'error': str(e)}

    async def stream_exchange_data(
            self,
            endpoint: str,
            session_id: str,
            client_id: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream exchange data (market, portfolio, orders) from the exchange simulator.
        
        Args:
            endpoint: The endpoint of the simulator
            session_id: The session ID
            client_id: The client ID
            
        Yields:
            Dict with comprehensive exchange data updates
        """
        with optional_trace_span(self.tracer, "stream_exchange_data_rpc") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("client_id", client_id)
            span.set_attribute("endpoint", endpoint)

            logger.info(f"Attempting to create exchange data stream: endpoint={endpoint}, session={session_id}")
            
            try:
                # Get channel and stub
                channel, stub = await self.get_channel(endpoint)
                logger.info("Successfully obtained gRPC channel and stub")

                # Create stream request
                request = StreamRequest(
                    session_id=session_id,
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

                # Stream processing
                try:
                    async for data in stream:
                        logger.debug(f"Received raw exchange data update")
                        
                        # Convert and yield data
                        converted_data = _convert_stream_data(data)
                        yield converted_data
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
        """
        Make the actual heartbeat request.

        Args:
            endpoint: The endpoint of the simulator
            session_id: The session ID
            client_id: The client ID

        Returns:
            Dict with heartbeat results
        """
        _, stub = await self.get_channel(endpoint)

        request = HeartbeatRequest(
            client_timestamp=int(time.time() * 1000)
        )

        try:
            # Add wait_for_ready=True and increase timeout to 10 seconds
            logger.info(f"Sending heartbeat to simulator at {endpoint} for session {session_id}")
            response = await stub.Heartbeat(
                request,
                timeout=10,
                wait_for_ready=True
            )

            logger.info(
                f"Received heartbeat response from simulator: success={response.success}, timestamp={response.server_timestamp}")

            return {
                'success': response.success,
                'server_timestamp': response.server_timestamp
            }
        except grpc.aio.AioRpcError as e:
            logger.debug(f"gRPC error sending heartbeat ({e.code()}): {e.details()}")
            track_circuit_breaker_failure("exchange_service")
            raise
        except Exception as e:
            logger.warning(f"Unexpected error in _heartbeat_request: {e}")
            track_circuit_breaker_failure("exchange_service")
            raise
