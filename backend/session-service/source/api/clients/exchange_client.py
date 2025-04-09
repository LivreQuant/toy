"""
Exchange service gRPC client.
Handles communication with the exchange simulator service using gRPC.
"""
import logging
import asyncio
import time
import grpc
from typing import Dict, List, Any, AsyncGenerator
from opentelemetry import trace

from source.utils.circuit_breaker import CircuitBreaker, CircuitOpenError

from source.utils.metrics import track_external_request, track_circuit_breaker_state, track_circuit_breaker_failure
from source.utils.tracing import optional_trace_span

from source.api.grpc.exchange_simulator_pb2 import (
    StartSimulatorRequest,
    StopSimulatorRequest,
    StreamRequest,
    HeartbeatRequest,
    GetSimulatorStatusRequest,
    ExchangeDataUpdate,
)
from source.api.grpc.exchange_simulator_pb2_grpc import ExchangeSimulatorStub

logger = logging.getLogger('exchange_client')


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
        self.circuit_breaker.on_state_change(self._on_circuit_state_change)

        # Create tracer
        self.tracer = trace.get_tracer("exchange_client")

    async def send_heartbeat_with_ttl(self, endpoint, session_id, client_id):
        """Send heartbeat with TTL that will automatically expire simulators if not renewed"""
        try:
            request = HeartbeatRequest(
                session_id=session_id,
                client_id=client_id,
                client_timestamp=int(time.time() * 1000),
                # ttl_seconds=ttl_seconds # Assuming this field exists in proto
            )
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

    def _on_circuit_state_change(self, name, old_state, new_state):
        """Handle circuit breaker state changes"""
        logger.info(f"Circuit breaker '{name}' state change: {old_state.value} -> {new_state.value}")
        track_circuit_breaker_state("exchange_service", new_state.value)

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

    async def start_simulator(
            self,
            endpoint: str,
            session_id: str,
            user_id: str,
    ) -> Dict[str, Any]:
        """
        Start a simulator instance

        Args:
            endpoint: The endpoint of the exchange manager service
            session_id: The session ID
            user_id: The user ID

        Returns:
            Dict with start results
        """
        with optional_trace_span(self.tracer, "start_simulator_rpc") as span:
            span.set_attribute("rpc.service", "ExchangeSimulator")
            span.set_attribute("rpc.method", "StartSimulator")
            span.set_attribute("net.peer.name", endpoint)
            span.set_attribute("app.session_id", session_id)
            span.set_attribute("app.user_id", user_id)

            try:
                # Execute request with circuit breaker
                response = await self.circuit_breaker.execute(
                    self._start_simulator_request,
                    endpoint, session_id, user_id
                )
                span.set_attribute("app.success", response.get('success', False))
                if response.get('simulator_id'):
                    span.set_attribute("app.simulator_id", response['simulator_id'])
                if response.get('error'):
                    span.set_attribute("error.message", response['error'])
                return response
            except CircuitOpenError as e:
                logger.warning(f"Circuit open for exchange service (start_simulator): {e}")
                span.set_attribute("error.message", "Exchange service unavailable (Circuit Open)")
                span.set_attribute("app.circuit_open", True)
                track_circuit_breaker_failure("exchange_service")  # Track failure
                return {'success': False, 'error': 'Exchange service unavailable'}
            except Exception as e:
                logger.error(f"Error starting simulator via gRPC: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error.message", str(e))
                return {'success': False, 'error': str(e)}

    async def _start_simulator_request(
            self,
            endpoint: str,
            session_id: str,
            user_id: str,
    ) -> Dict[str, Any]:
        """Make the actual start simulator request"""
        _, stub = await self.get_channel(endpoint)

        request = StartSimulatorRequest(
            session_id=session_id,
            user_id=user_id,
        )

        start_time = time.time()
        try:
            response = await stub.StartSimulator(request, timeout=15)  # Increased timeout slightly
            duration = time.time() - start_time
            track_external_request("exchange_service", "StartSimulator", 200, duration)

            return {
                'success': response.success,
                'simulator_id': response.simulator_id,
                'error': response.error_message if not response.success else None
            }
        except grpc.aio.AioRpcError as e:
            duration = time.time() - start_time
            track_external_request("exchange_service", "StartSimulator", e.code(), duration)
            logger.error(f"gRPC error starting simulator ({e.code()}): {e.details()}")
            track_circuit_breaker_failure("exchange_service")  # Track failure
            raise  # Re-raise for circuit breaker
        except Exception as e:
            duration = time.time() - start_time
            track_external_request("exchange_service", "StartSimulator", 500, duration)  # Generic error
            logger.error(f"Unexpected error in _start_simulator_request: {e}")
            track_circuit_breaker_failure("exchange_service")  # Track failure
            raise  # Re-raise for circuit breaker

    async def stop_simulator(self, endpoint: str, session_id: str) -> Dict[str, Any]:
        """
        Stop a simulator instance

        Args:
            endpoint: The endpoint of the simulator
            session_id: The session ID

        Returns:
            Dict with stop results
        """
        with optional_trace_span(self.tracer, "stop_simulator_rpc") as span:
            span.set_attribute("rpc.service", "ExchangeSimulator")
            span.set_attribute("rpc.method", "StopSimulator")
            span.set_attribute("net.peer.name", endpoint)
            span.set_attribute("app.session_id", session_id)
            try:
                # Execute request with circuit breaker
                response = await self.circuit_breaker.execute(
                    self._stop_simulator_request, endpoint, session_id
                )
                span.set_attribute("app.success", response.get('success', False))
                if response.get('error'):
                    span.set_attribute("error.message", response['error'])
                return response
            except CircuitOpenError as e:
                logger.warning(f"Circuit open for exchange service (stop_simulator): {e}")
                span.set_attribute("error.message", "Exchange service unavailable (Circuit Open)")
                span.set_attribute("app.circuit_open", True)
                track_circuit_breaker_failure("exchange_service")
                return {'success': False, 'error': 'Exchange service unavailable'}
            except Exception as e:
                logger.error(f"Error stopping simulator via gRPC: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error.message", str(e))
                return {'success': False, 'error': str(e)}

    async def _stop_simulator_request(self, endpoint: str, session_id: str) -> Dict[str, Any]:
        """Make the actual stop simulator request"""
        _, stub = await self.get_channel(endpoint)

        request = StopSimulatorRequest(
            session_id=session_id
        )

        start_time = time.time()
        try:
            response = await stub.StopSimulator(request, timeout=10)
            duration = time.time() - start_time
            track_external_request("exchange_service", "StopSimulator", 200, duration)

            return {
                'success': response.success,
                'error': response.error_message if not response.success else None
            }
        except grpc.aio.AioRpcError as e:
            duration = time.time() - start_time
            track_external_request("exchange_service", "StopSimulator", e.code(), duration)
            logger.error(f"gRPC error stopping simulator ({e.code()}): {e.details()}")
            track_circuit_breaker_failure("exchange_service")
            raise  # Re-raise for circuit breaker
        except Exception as e:
            duration = time.time() - start_time
            track_external_request("exchange_service", "StopSimulator", 500, duration)
            logger.error(f"Unexpected error in _stop_simulator_request: {e}")
            track_circuit_breaker_failure("exchange_service")
            raise  # Re-raise for circuit breaker

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
        with optional_trace_span(self.tracer, "heartbeat_rpc", kind=trace.SpanKind.CLIENT) as span:
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
            session_id=session_id,
            client_id=client_id,
            client_timestamp=int(time.time() * 1000)
            # Add ttl_seconds if needed based on proto definition
        )

        start_time = time.time()
        try:
            response = await stub.Heartbeat(request, timeout=5)
            duration = time.time() - start_time
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
        with optional_trace_span(self.tracer, "stream_exchange_data_rpc", kind=trace.SpanKind.CLIENT) as span:
            span.set_attribute("rpc.service", "ExchangeSimulator")
            span.set_attribute("rpc.method", "StreamExchangeData")
            span.set_attribute("net.peer.name", endpoint)
            span.set_attribute("app.session_id", session_id)
            span.set_attribute("app.client_id", client_id)

            _, stub = await self.get_channel(endpoint)

            request = StreamRequest(
                session_id=session_id,
                client_id=client_id,
            )

            # This streaming endpoint doesn't use circuit breaker to allow long-running streams
            stream = None
            try:
                # Updated RPC method name
                stream = stub.StreamExchangeData(request)
                logger.info(f"Started gRPC exchange data stream to {endpoint} for session {session_id}")
                span.add_event("Stream started")

                async for data in stream:
                    # Convert protobuf message to dictionary using updated method
                    yield self._convert_stream_data(data)

            except grpc.aio.AioRpcError as e:
                span.record_exception(e)
                span.set_attribute("rpc.grpc.status_code", e.code())
                if e.code() == grpc.StatusCode.CANCELLED:
                    logger.info(f"Exchange data stream cancelled for session {session_id}")
                    span.add_event("Stream cancelled by client or server")
                elif e.code() == grpc.StatusCode.UNAVAILABLE:
                    logger.error(f"Exchange service unavailable for stream: {endpoint}. Details: {e.details()}")
                    span.set_attribute("error.message", "Service unavailable")
                    # Optionally trigger circuit breaker manually here if needed for streams
                    # self.circuit_breaker.record_failure() ? - needs careful thought
                else:
                    logger.error(f"gRPC error in exchange data stream ({e.code()}): {e.details()}")
                    span.set_attribute("error.message", e.details())
                raise  # Re-raise error to signal stream termination
            except Exception as e:
                logger.error(f"Unexpected error in exchange data stream for session {session_id}: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error.message", str(e))
                raise  # Re-raise error
            finally:
                # Attempt to cancel the stream if it exists and wasn't cancelled normally
                # This might be redundant if the loop exit implies cancellation/error
                # if stream and hasattr(stream, 'cancel') and not stream.cancelled():
                #    stream.cancel()
                logger.info(f"Exchange data stream finished or errored for session {session_id}")
                span.add_event("Stream finished or errored")

    # Updated conversion function
    def _convert_stream_data(self, data: ExchangeDataUpdate) -> Dict[str, Any]:
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
        with optional_trace_span(self.tracer, "get_simulator_status_rpc") as span:
            span.set_attribute("rpc.service", "ExchangeSimulator")
            span.set_attribute("rpc.method", "GetSimulatorStatus")
            span.set_attribute("net.peer.name", endpoint)
            span.set_attribute("app.session_id", session_id)
            try:
                # Execute request with circuit breaker
                response = await self.circuit_breaker.execute(
                    self._get_simulator_status_request, endpoint, session_id
                )
                span.set_attribute("app.status", response.get('status', 'UNKNOWN'))
                if response.get('error'):
                    span.set_attribute("error.message", response['error'])
                return response
            except CircuitOpenError as e:
                logger.warning(f"Circuit open for exchange service (get_simulator_status): {e}")
                span.set_attribute("error.message", "Exchange service unavailable (Circuit Open)")
                span.set_attribute("app.circuit_open", True)
                track_circuit_breaker_failure("exchange_service")
                return {'status': 'UNKNOWN', 'error': 'Exchange service unavailable'}
            except Exception as e:
                logger.error(f"Error getting simulator status via gRPC: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error.message", str(e))
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

        start_time = time.time()
        try:
            # Increased timeout slightly as this might involve more work on simulator side
            response = await stub.GetSimulatorStatus(request, timeout=7)
            duration = time.time() - start_time
            track_external_request("exchange_service", "GetSimulatorStatus", 200, duration)

            return {
                'status': response.status,  # String status from proto
                # 'simulator_id': response.simulator_id, # Avoid sending back
                'uptime_seconds': response.uptime_seconds,
                'error': response.error_message if response.status == 'ERROR' else None
            }
        except grpc.aio.AioRpcError as e:
            duration = time.time() - start_time
            track_external_request("exchange_service", "GetSimulatorStatus", e.code(), duration)
            logger.error(f"gRPC error getting simulator status ({e.code()}): {e.details()}")
            track_circuit_breaker_failure("exchange_service")
            raise  # Re-raise for circuit breaker
        except Exception as e:
            duration = time.time() - start_time
            track_external_request("exchange_service", "GetSimulatorStatus", 500, duration)
            logger.error(f"Unexpected error in _get_simulator_status_request: {e}")
            track_circuit_breaker_failure("exchange_service")
            raise  # Re-raise for circuit breaker
