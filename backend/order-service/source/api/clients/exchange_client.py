import logging
import grpc
import asyncio
import time
from typing import Dict, Any, Optional

from source.utils.circuit_breaker import CircuitBreaker, CircuitOpenError
from source.models.order import Order
from source.models.enums import OrderStatus
from source.api.grpc.exchange_simulator_pb2 import (
    SubmitOrderRequest, CancelOrderRequest, GetOrderStatusRequest
)
from source.api.grpc.exchange_simulator_pb2_grpc import ExchangeSimulatorStub
from source.utils.metrics import track_exchange_request, set_circuit_state, track_circuit_failure
from opentelemetry import trace

from source.utils.tracing import optional_trace_span

logger = logging.getLogger('exchange_client')

class ExchangeClient:
    """Client for communicating with exchange simulator via gRPC"""

    def __init__(self):
        """Initialize exchange client"""
        self.channels = {}  # endpoint -> channel
        self.stubs = {}  # endpoint -> stub
        self._conn_lock = asyncio.Lock()
        self.tracer = trace.get_tracer("exchange_client")

        # Initialize circuit breaker
        self.breaker = CircuitBreaker(
            name="exchange_service",
            failure_threshold=5,
            reset_timeout_ms=30000  # 30 seconds
        )

    async def get_channel(self, endpoint: str):
        """Get or create a gRPC channel to the endpoint"""
        with optional_trace_span(self.tracer, "get_channel") as span:
            span.set_attribute("endpoint", endpoint)

            async with self._conn_lock:
                if endpoint in self.channels:
                    span.set_attribute("channel_exists", True)
                    return self.channels[endpoint], self.stubs[endpoint]

                span.set_attribute("channel_exists", False)

                # Create channel options
                options = [
                    ('grpc.keepalive_time_ms', 10000),  # 10 seconds
                    ('grpc.keepalive_timeout_ms', 5000),  # 5 seconds
                    ('grpc.keepalive_permit_without_calls', 1),
                    ('grpc.http2.max_pings_without_data', 0),
                    ('grpc.http2.min_time_between_pings_ms', 10000),
                    ('grpc.http2.min_ping_interval_without_data_ms', 5000)
                ]

                try:
                    # Create channel
                    channel = grpc.aio.insecure_channel(endpoint, options=options)
                    stub = ExchangeSimulatorStub(channel)

                    # Store for reuse
                    self.channels[endpoint] = channel
                    self.stubs[endpoint] = stub

                    span.set_attribute("success", True)
                    return channel, stub
                except Exception as e:
                    span.record_exception(e)
                    span.set_attribute("success", False)
                    logger.error(f"Failed to create gRPC channel to {endpoint}: {e}")
                    raise

    async def close(self):
        """Close all gRPC channels"""
        with optional_trace_span(self.tracer, "close") as span:
            for endpoint, channel in list(self.channels.items()):
                try:
                    await channel.close()
                    span.set_attribute(f"closed_{endpoint}", True)
                except Exception as e:
                    span.set_attribute(f"closed_{endpoint}", False)
                    logger.error(f"Error closing channel to {endpoint}: {e}")

            self.channels.clear()
            self.stubs.clear()

    async def submit_order(self, order: Order, simulator_endpoint: str) -> Dict[str, Any]:
        """Submit an order to the exchange simulator"""
        with optional_trace_span(self.tracer, "submit_order") as span:
            span.set_attribute("order_id", order.order_id)
            span.set_attribute("symbol", order.symbol)
            span.set_attribute("side", order.side.value)
            span.set_attribute("order_type", order.order_type.value)
            span.set_attribute("endpoint", simulator_endpoint)

            # Use circuit breaker for gRPC call
            try:
                # Update circuit state in metrics
                set_circuit_state("exchange_service", self.breaker.state.name)

                # Execute with circuit breaker
                start_time = time.time()
                result = await self.breaker.execute(
                    self._submit_order_request,
                    order,
                    simulator_endpoint
                )
                duration = time.time() - start_time

                # Record metrics
                success = result.get('success', False)
                track_exchange_request("submit_order", success, duration)

                span.set_attribute("success", success)
                if not success:
                    span.set_attribute("error", result.get('error', 'Unknown error'))

                return result
            except CircuitOpenError:
                track_circuit_failure("exchange_service")
                span.set_attribute("circuit_open", True)
                span.set_attribute("success", False)
                logger.warning("Exchange service circuit breaker open")
                return {
                    "success": False,
                    "error": "Exchange service unavailable due to repeated failures",
                    "order_id": order.order_id
                }

    async def _submit_order_request(self, order: Order, endpoint: str) -> Dict[str, Any]:
        """Make the actual order submission request"""
        with optional_trace_span(self.tracer, "_submit_order_request") as span:
            try:
                # Get gRPC connection
                _, stub = await self.get_channel(endpoint)

                # Convert order side and type to gRPC enum values
                side_enum = 0 if order.side == "BUY" else 1  # 0=BUY, 1=SELL
                type_enum = 0 if order.order_type == "MARKET" else 1  # 0=MARKET, 1=LIMIT

                # Create gRPC request
                request = SubmitOrderRequest(
                    session_id=order.session_id,
                    symbol=order.symbol,
                    side=side_enum,
                    quantity=float(order.quantity),
                    price=float(order.price) if order.price is not None else 0,
                    type=type_enum,
                    request_id=order.request_id or f"order-{int(time.time())}-{order.order_id}"
                )

                span.set_attribute("request_id", request.request_id)

                # Call gRPC service
                response = await stub.SubmitOrder(request, timeout=5)
                span.set_attribute("response.success", response.success)

                if not response.success:
                    logger.warning(f"Order submission failed: {response.error_message}")
                    span.set_attribute("error", response.error_message)
                    return {
                        "success": False,
                        "error": response.error_message,
                        "order_id": order.order_id
                    }

                span.set_attribute("response.order_id", response.order_id)
                return {
                    "success": True,
                    "order_id": response.order_id or order.order_id
                }

            except grpc.aio.AioRpcError as e:
                status_code = e.code()
                span.set_attribute("grpc.status_code", str(status_code))
                span.set_attribute("error", e.details())

                if status_code == grpc.StatusCode.UNAVAILABLE:
                    logger.error(f"Exchange unavailable: {e.details()}")
                    return {
                        "success": False,
                        "error": "Exchange service unavailable, please try again later",
                        "order_id": order.order_id
                    }
                elif status_code == grpc.StatusCode.DEADLINE_EXCEEDED:
                    logger.error(f"Exchange request timed out: {e.details()}")
                    return {
                        "success": False,
                        "error": "Exchange service timed out, please try again",
                        "order_id": order.order_id
                    }
                logger.error(f"gRPC error ({status_code}): {e.details()}")
                return {
                    "success": False,
                    "error": f"Communication error: {e.details()}",
                    "order_id": order.order_id
                }
            except Exception as e:
                span.record_exception(e)
                logger.error(f"Error submitting order to exchange: {e}")
                return {
                    "success": False,
                    "error": f"Exchange communication error: {str(e)}",
                    "order_id": order.order_id
                }

    async def cancel_order(self, order: Order, simulator_endpoint: str) -> Dict[str, Any]:
        """Cancel an order on the exchange simulator"""
        with optional_trace_span(self.tracer, "cancel_order") as span:
            span.set_attribute("order_id", order.order_id)
            span.set_attribute("endpoint", simulator_endpoint)

            # Use circuit breaker for gRPC call
            try:
                # Update circuit state in metrics
                set_circuit_state("exchange_service", self.breaker.state.name)

                # Execute with circuit breaker
                start_time = time.time()
                result = await self.breaker.execute(
                    self._cancel_order_request,
                    order,
                    simulator_endpoint
                )
                duration = time.time() - start_time

                # Record metrics
                success = result.get('success', False)
                track_exchange_request("cancel_order", success, duration)

                span.set_attribute("success", success)
                if not success:
                    span.set_attribute("error", result.get('error', 'Unknown error'))

                return result
            except CircuitOpenError:
                track_circuit_failure("exchange_service")
                span.set_attribute("circuit_open", True)
                span.set_attribute("success", False)
                logger.warning("Exchange service circuit breaker open")
                return {
                    "success": False,
                    "error": "Exchange service unavailable due to repeated failures"
                }

    async def _cancel_order_request(self, order: Order, endpoint: str) -> Dict[str, Any]:
        """Make the actual order cancellation request"""
        with optional_trace_span(self.tracer, "_cancel_order_request") as span:
            try:
                # Get gRPC connection
                _, stub = await self.get_channel(endpoint)

                # Create gRPC request
                request = CancelOrderRequest(
                    session_id=order.session_id,
                    order_id=order.order_id
                )

                # Call gRPC service
                response = await stub.CancelOrder(request, timeout=5)
                span.set_attribute("response.success", response.success)

                if not response.success:
                    logger.warning(f"Order cancellation failed: {response.error_message}")
                    span.set_attribute("error", response.error_message)
                    return {
                        "success": False,
                        "error": response.error_message
                    }

                return {
                    "success": True
                }

            except grpc.aio.AioRpcError as e:
                status_code = e.code()
                span.set_attribute("grpc.status_code", str(status_code))
                span.set_attribute("error", e.details())

                if status_code == grpc.StatusCode.UNAVAILABLE:
                    logger.error(f"Exchange unavailable: {e.details()}")
                    return {
                        "success": False,
                        "error": "Exchange service unavailable, please try again later"
                    }
                logger.error(f"gRPC error ({status_code}): {e.details()}")
                return {
                    "success": False,
                    "error": f"Communication error: {e.details()}"
                }
            except Exception as e:
                span.record_exception(e)
                logger.error(f"Error cancelling order on exchange: {e}")
                return {
                    "success": False,
                    "error": f"Exchange communication error: {str(e)}"
                }

    async def get_order_status(self, order: Order, simulator_endpoint: str) -> Dict[str, Any]:
        """Get order status from the exchange simulator"""
        with optional_trace_span(self.tracer, "get_order_status") as span:
            span.set_attribute("order_id", order.order_id)
            span.set_attribute("endpoint", simulator_endpoint)

            # Use circuit breaker for gRPC call
            try:
                # Update circuit state in metrics
                set_circuit_state("exchange_service", self.breaker.state.name)

                # Execute with circuit breaker
                start_time = time.time()
                result = await self.breaker.execute(
                    self._get_order_status_request,
                    order,
                    simulator_endpoint
                )
                duration = time.time() - start_time

                # Record metrics
                success = result.get('success', False)
                track_exchange_request("get_order_status", success, duration)

                span.set_attribute("success", success)
                if not success:
                    span.set_attribute("error", result.get('error', 'Unknown error'))

                return result
            except CircuitOpenError:
                track_circuit_failure("exchange_service")
                span.set_attribute("circuit_open", True)
                span.set_attribute("success", False)
                logger.warning("Exchange service circuit breaker open")
                return {
                    "success": False,
                    "error": "Exchange service unavailable due to repeated failures"
                }

    async def _get_order_status_request(self, order: Order, endpoint: str) -> Dict[str, Any]:
        """Make the actual order status request"""
        with optional_trace_span(self.tracer, "_get_order_status_request") as span:
            try:
                # Get gRPC connection
                _, stub = await self.get_channel(endpoint)

                # Create gRPC request
                request = GetOrderStatusRequest(
                    session_id=order.session_id,
                    order_id=order.order_id
                )

                # Call gRPC service
                response = await stub.GetOrderStatus(request, timeout=5)
                span.set_attribute("response.status", response.status)

                # Map status enum to string
                status_map = {
                    0: OrderStatus.REJECTED,  # UNKNOWN
                    1: OrderStatus.NEW,  # NEW
                    2: OrderStatus.PARTIALLY_FILLED,  # PARTIALLY_FILLED
                    3: OrderStatus.FILLED,  # FILLED
                    4: OrderStatus.CANCELED,  # CANCELED
                    5: OrderStatus.REJECTED  # REJECTED
                }
                status = status_map.get(response.status, OrderStatus.REJECTED)

                span.set_attribute("filled_quantity", float(response.filled_quantity))
                span.set_attribute("avg_price", float(response.avg_price))

                return {
                    "success": True,
                    "status": status,
                    "filled_quantity": float(response.filled_quantity),
                    "avg_price": float(response.avg_price),
                    "error_message": response.error_message
                }

            except grpc.aio.AioRpcError as e:
                status_code = e.code()
                span.set_attribute("grpc.status_code", str(status_code))
                span.set_attribute("error", e.details())

                if status_code == grpc.StatusCode.UNAVAILABLE:
                    logger.error(f"Exchange unavailable: {e.details()}")
                    return {
                        "success": False,
                        "error": "Exchange service unavailable, please try again later"
                    }
                logger.error(f"gRPC error ({status_code}): {e.details()}")
                return {
                    "success": False,
                    "error": f"Communication error: {e.details()}"
                }
            except Exception as e:
                span.record_exception(e)
                logger.error(f"Error getting order status from exchange: {e}")
                return {
                    "success": False,
                    "error": f"Exchange communication error: {str(e)}"
                }
