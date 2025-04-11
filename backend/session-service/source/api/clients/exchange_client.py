"""
Exchange service gRPC client.
Handles communication with the exchange simulator service using gRPC.
"""
import logging
import asyncio
import time
import grpc
from typing import Dict, Any, AsyncGenerator
from opentelemetry import trace

from source.utils.circuit_breaker import CircuitBreaker, CircuitOpenError

from source.utils.metrics import track_circuit_breaker_state, track_circuit_breaker_failure
from source.utils.tracing import optional_trace_span

from source.api.grpc.exchange_simulator_pb2 import (
    StreamRequest,
    ExchangeDataUpdate,
    HeartbeatRequest,
    HeartbeatResponse,
)
from source.api.grpc.exchange_simulator_pb2_grpc import ExchangeSimulatorStub

logger = logging.getLogger('exchange_client')


def _convert_stream_data(data: ExchangeDataUpdate) -> Dict[str, Any]:
    """Convert ExchangeDataUpdate protobuf message to dictionary"""
    result = {
        'timestamp': data.timestamp,
        'marketData': [],
        'orderUpdates': [],  # Added field
        'portfolio': None
    }

    # Convert market data
    for item in data.market_data:
        # Assuming MarketData fields from proto: symbol, bid, ask, bid_size, ask_size, last_price, last_size
        result['marketData'].append({
            'symbol': item.symbol,
            'bid': item.bid,
            'ask': item.ask,
            'bidSize': item.bid_size,
            'askSize': item.ask_size,
            'lastPrice': item.last_price,
            'lastSize': item.last_size
            # Add timestamp if it exists in MarketData proto
        })

    # Convert order updates (Added)
    for item in data.order_updates:
        # Assuming OrderUpdate fields from proto: order_id, symbol, status, filled_quantity, average_price
        result['orderUpdates'].append({
            'orderId': item.order_id,
            'symbol': item.symbol,
            'status': item.status,  # Keep as string from proto
            'filledQuantity': item.filled_quantity,
            'averagePrice': item.average_price
        })

    # Convert portfolio if present
    if data.HasField('portfolio'):
        portfolio = data.portfolio
        # Assuming PortfolioStatus fields: positions, cash_balance, total_value
        positions_list = []
        for pos in portfolio.positions:
            # Assuming Position fields: symbol, quantity, average_cost, market_value
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


def _on_circuit_state_change(name, old_state, new_state, info=None):
    """Handle circuit breaker state changes"""
    logger.info(f"Circuit breaker '{name}' state change: {old_state.value} -> {new_state.value}")
    track_circuit_breaker_state("exchange_service", new_state.value)


class ExchangeClient:
    """Client for the exchange simulator gRPC service"""

    def __init__(self):
        """Initialize the exchange client"""
        self.channels = {}  # endpoint -> channel
        self.stubs = {}  # endpoint -> stub
        self._conn_lock = asyncio.Lock()

        # Create circuit breaker
        self.circuit_breaker = CircuitBreaker(
            name="exchange_service",
            failure_threshold=3,
            reset_timeout_ms=30000  # 30 seconds
        )

        # Register callback for circuit breaker state changes
        self.circuit_breaker.on_state_change(_on_circuit_state_change)

        # Create tracer
        self.tracer = trace.get_tracer("exchange_client")

    async def send_heartbeat(self, endpoint, session_id, client_id):
        """Send heartbeat with TTL that will automatically expire simulators if not renewed"""
        try:
            # Use the internal request method with circuit breaker
            response = await self.circuit_breaker.execute(
                self._heartbeat_request, endpoint, session_id, client_id  # Pass args for _heartbeat_request
            )
            return response
        except CircuitOpenError as e:
            logger.warning(f"Circuit open for exchange service (heartbeat): {e}")
            return {'success': False, 'error': 'Exchange service unavailable'}
        except Exception as e:
            logger.error(f"Error sending heartbeat with TTL: {e}")
            return {'success': False, 'error': str(e)}

    async def get_channel(self, endpoint: str):
        """Get or create a gRPC channel to the endpoint"""
        async with self._conn_lock:
            if endpoint in self.channels:
                # Basic check if channel is usable (more robust checks might be needed)
                try:
                    # A simple connectivity check (may not always work depending on server/proxy)
                    # await self.channels[endpoint].get_state(try_to_connect=True)
                    # Pass if channel exists, assume usable for now
                    pass
                except Exception:
                    logger.warning(f"Recreating potentially unhealthy channel to {endpoint}")
                    # Attempt to close before recreating
                    try:
                        await self.channels[endpoint].close()
                    except Exception as close_err:
                        logger.error(f"Error closing channel before recreation: {close_err}")
                    del self.channels[endpoint]
                    del self.stubs[endpoint]

            if endpoint not in self.channels:
                logger.info(f"Creating new gRPC channel to {endpoint}")
                # Create channel options
                options = [
                    ('grpc.keepalive_time_ms', 10000),  # Send keepalive every 10s
                    ('grpc.keepalive_timeout_ms', 5000),  # Wait 5s for pong ack
                    ('grpc.keepalive_permit_without_calls', 1),  # Allow keepalive pings when there are no calls
                    ('grpc.http2.max_pings_without_data', 0),  # Allow pings even without data
                    ('grpc.http2.min_time_between_pings_ms', 10000),  # Allow pings every 10s
                    ('grpc.http2.min_ping_interval_without_data_ms', 5000)  # Allow pings without data every 5s
                ]

                # Create channel
                channel = grpc.aio.insecure_channel(endpoint, options=options)
                stub = ExchangeSimulatorStub(channel)

                # Store for reuse
                self.channels[endpoint] = channel
                self.stubs[endpoint] = stub

            return self.channels[endpoint], self.stubs[endpoint]

    async def close(self):
        """Close all gRPC channels"""
        async with self._conn_lock:
            logger.info(f"Closing {len(self.channels)} gRPC channels.")
            for endpoint, channel in self.channels.items():
                try:
                    await channel.close()
                    logger.debug(f"Closed channel to {endpoint}")
                except Exception as e:
                    logger.error(f"Error closing channel to {endpoint}: {e}")

            self.channels.clear()
            self.stubs.clear()
        logger.info("Finished closing gRPC channels.")

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
        # Heartbeats are frequent and less critical, might bypass circuit breaker
        # or use a separate one with different settings if needed.
        # For now, keep using the main one.
        with optional_trace_span(self.tracer, "heartbeat_rpc") as span:
            span.set_attribute("rpc.service", "ExchangeSimulator")
            span.set_attribute("rpc.method", "Heartbeat")
            span.set_attribute("net.peer.name", endpoint)
            span.set_attribute("app.session_id", session_id)
            try:
                # Execute request with circuit breaker
                response = await self.circuit_breaker.execute(
                    self._heartbeat_request, endpoint, session_id, client_id
                )
                span.set_attribute("app.success", response.get('success', False))
                return response
            except CircuitOpenError as e:
                # Log less severely for heartbeats maybe
                logger.debug(f"Circuit open for exchange service (heartbeat): {e}")
                span.set_attribute("error.message", "Exchange service unavailable (Circuit Open)")
                span.set_attribute("app.circuit_open", True)
                track_circuit_breaker_failure("exchange_service")
                return {'success': False, 'error': 'Exchange service unavailable'}
            except Exception as e:
                logger.warning(f"Error sending heartbeat via gRPC: {e}")  # Log as warning
                span.record_exception(e)
                span.set_attribute("error.message", str(e))
                return {'success': False, 'error': str(e)}

    async def _heartbeat_request(self, endpoint: str, session_id: str, client_id: str) -> Dict[str, Any]:
        """Make the actual heartbeat request"""
        _, stub = await self.get_channel(endpoint)

        request = HeartbeatRequest(
            client_timestamp=int(time.time() * 1000)
        )

        start_time = time.time()
        try:
            response = await stub.Heartbeat(request, timeout=5)
            # Metrics for heartbeat might be too noisy, consider sampling or removing
            # track_external_request("exchange_service", "Heartbeat", 200, duration)

            return {
                'success': response.success,
                'server_timestamp': response.server_timestamp
            }
        except grpc.aio.AioRpcError as e:
            duration = time.time() - start_time
            # track_external_request("exchange_service", "Heartbeat", e.code(), duration)
            # Log less severely
            logger.debug(f"gRPC error sending heartbeat ({e.code()}): {e.details()}")
            track_circuit_breaker_failure("exchange_service")
            raise  # Re-raise for circuit breaker
        except Exception as e:
            # duration = time.time() - start_time
            # track_external_request("exchange_service", "Heartbeat", 500, duration)
            logger.warning(f"Unexpected error in _heartbeat_request: {e}")
            track_circuit_breaker_failure("exchange_service")
            raise  # Re-raise for circuit breaker

    # Renamed method
    async def stream_exchange_data(
            self,
            endpoint: str,
            session_id: str,
            client_id: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream exchange data (market, portfolio, orders) from the exchange simulator (renamed)

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

            logger.info(f"Attempting to create exchange data stream")
            logger.info(f"Endpoint: {endpoint}")
            logger.info(f"Session ID: {session_id}")
            logger.info(f"Client ID: {client_id}")
            
            try:
                # Get channel and stub
                channel, stub = await self.get_channel(endpoint)
                logger.info("Successfully obtained gRPC channel and stub")

                # Create stream request
                request = StreamRequest(
                    session_id=session_id,
                    client_id=client_id,
                )
                logger.info("Created StreamRequest")

                # Initiate streaming RPC
                try:
                    stream = stub.StreamExchangeData(request)
                    logger.info("Initiated StreamExchangeData RPC")
                except Exception as rpc_init_error:
                    logger.error(f"Failed to initiate streaming RPC: {rpc_init_error}")
                    span.record_exception(rpc_init_error)
                    raise

                # Stream processing
                try:
                    async for data in stream:
                        logger.debug(f"Received raw exchange data: {data}")
                        
                        # Convert and yield data
                        converted_data = _convert_stream_data(data)
                        logger.debug(f"Converted exchange data: {converted_data}")
                        
                        yield converted_data
                except Exception as stream_error:
                    logger.error(f"Error in stream processing: {stream_error}")
                    span.record_exception(stream_error)
                    raise

            except Exception as e:
                logger.error(f"Comprehensive exchange data stream error: {e}")
                logger.error(f"Error details:", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                raise
