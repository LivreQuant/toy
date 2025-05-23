# source/clients/exchange_client.py
import logging
import grpc
import asyncio
import time
from typing import Dict, Any

from source.utils.circuit_breaker import CircuitBreaker, CircuitOpenError
from source.api.grpc.conviction_exchange_interface_pb2 import (
    BatchConvictionRequest, BatchCancelRequest, ConvictionRequest
)
from source.api.grpc.conviction_exchange_interface_pb2_grpc import ConvictionExchangeSimulatorStub
from source.utils.metrics import track_exchange_request, set_circuit_state, track_circuit_failure

logger = logging.getLogger('exchange_client')


class ExchangeClient:
    """Client for communicating with exchange simulator via gRPC"""

    def __init__(self):
        """Initialize exchange client"""
        self.channels = {}  # endpoint -> channel
        self.stubs = {}  # endpoint -> stub
        self._conn_lock = asyncio.Lock()

        # Create circuit breaker
        self.breaker = CircuitBreaker(
            name="exchange_service",
            failure_threshold=5,
            reset_timeout_ms=30000  # 30 seconds
        )

    async def get_channel(self, endpoint: str):
        """Get or create a gRPC channel to the endpoint"""
        async with self._conn_lock:
            if endpoint in self.channels:
                return self.channels[endpoint], self.stubs[endpoint]

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
                stub = ConvictionExchangeSimulatorStub(channel)

                # Store for reuse
                self.channels[endpoint] = channel
                self.stubs[endpoint] = stub

                return channel, stub
            except Exception as e:
                logger.error(f"Failed to create gRPC channel to {endpoint}: {e}")
                raise

    async def close(self):
        """Close all gRPC channels"""
        for endpoint, channel in list(self.channels.items()):
            try:
                await channel.close()
            except Exception as e:
                logger.error(f"Error closing channel to {endpoint}: {e}")

        self.channels.clear()
        self.stubs.clear()

    async def submit_convictions(self, batch_request: Dict[str, Any], endpoint: str) -> Dict[str, Any]:
        """
        Submit a batch of convictions to the exchange simulator
        
        Args:
            batch_request: convictions array
            endpoint: Exchange endpoint
            
        Returns:
            Dictionary with success flag and results
        """
        try:
            # Use circuit breaker for gRPC call
            set_circuit_state("exchange_service", self.breaker.state.name)

            # Execute with circuit breaker
            start_time = time.time()
            result = await self.breaker.execute(
                self._submit_convictions_request,
                batch_request,
                endpoint
            )
            duration = time.time() - start_time

            # Record metrics
            success = result.get('success', False)
            track_exchange_request("submit_convictions_batch", success, duration)

            return result
        except CircuitOpenError:
            track_circuit_failure("exchange_service")
            logger.warning("Exchange service circuit breaker open")
            return {
                "success": False,
                "error": "Exchange service unavailable due to repeated failures",
                "results": []
            }

    async def _submit_convictions_request(self, batch_request: Dict[str, Any], endpoint: str) -> Dict[str, Any]:
        """Make the actual batch conviction submission request to gRPC service"""
        try:
            # Get gRPC connection
            _, stub = await self.get_channel(endpoint)

            # Prepare the gRPC request
            conviction_requests = []
            for conviction_data in batch_request["convictions"]:
                # Convert enum values
                side_enum = 0 if conviction_data["side"] == "BUY" else 1
                type_enum = 0 if conviction_data["type"] == "MARKET" else 1

                # Create ConvictionRequest for each conviction
                conviction_request = ConvictionRequest(
                    symbol=conviction_data["symbol"],
                    side=side_enum,
                    quantity=float(conviction_data["quantity"]),
                    price=float(conviction_data.get("price", 0)),
                    type=type_enum,
                    request_id=conviction_data.get("request_id", "")
                )
                conviction_requests.append(conviction_request)

            # Create the batch request
            grpc_request = BatchConvictionRequest(
                convictions=conviction_requests
            )

            # Call gRPC service with timeout
            response = await stub.SubmitConvictions(grpc_request, timeout=10)

            # Convert to dictionary format
            result = {
                "success": response.success,
                "error": response.error_message if hasattr(response, "error_message") else None,
                "results": []
            }

            # Process individual conviction results
            for conviction_result in response.results:
                result["results"].append({
                    "success": conviction_result.success,
                    "convictionId": conviction_result.conviction_id,
                    "error": conviction_result.error_message
                })

            return result

        except grpc.aio.AioRpcError as e:
            # Handle gRPC errors
            return self._handle_grpc_error(e, "submit_convictions")

        except Exception as e:
            logger.error(f"Unexpected error in submit_convictions: {e}")
            return {
                "success": False,
                "error": f"Exchange communication error: {str(e)}",
                "results": []
            }

    async def cancel_convictions(self, batch_request: Dict[str, Any], endpoint: str) -> Dict[str, Any]:
        """
        Cancel a batch of convictions on the exchange simulator
        
        Args:
            batch_request: conviction_ids array
            endpoint: Exchange endpoint
            
        Returns:
            Dictionary with success flag and results
        """
        try:
            # Use circuit breaker for gRPC call
            set_circuit_state("exchange_service", self.breaker.state.name)

            # Execute with circuit breaker
            start_time = time.time()
            result = await self.breaker.execute(
                self._cancel_convictions_request,
                batch_request,
                endpoint
            )
            duration = time.time() - start_time

            # Record metrics
            success = result.get('success', False)
            track_exchange_request("cancel_convictions_batch", success, duration)

            return result
        except CircuitOpenError:
            track_circuit_failure("exchange_service")
            logger.warning("Exchange service circuit breaker open")
            return {
                "success": False,
                "error": "Exchange service unavailable due to repeated failures",
                "results": []
            }

    async def _cancel_convictions_request(self, batch_request: Dict[str, Any], endpoint: str) -> Dict[str, Any]:
        """Make the actual batch cancel request to gRPC service"""
        try:
            # Get gRPC connection
            _, stub = await self.get_channel(endpoint)

            # Create the batch request
            grpc_request = BatchCancelRequest(
                conviction_ids=batch_request["conviction_ids"]
            )

            # Call gRPC service with timeout
            response = await stub.CancelConvictions(grpc_request, timeout=10)

            # Convert to dictionary format
            result = {
                "success": response.success,
                "error": response.error_message if hasattr(response, "error_message") else None,
                "results": []
            }

            # Process individual cancel results
            for cancel_result in response.results:
                result["results"].append({
                    "success": cancel_result.success,
                    "convictionId": cancel_result.conviction_id,
                    "error": cancel_result.error_message if hasattr(cancel_result, "error_message") else None
                })

            return result

        except grpc.aio.AioRpcError as e:
            # Handle gRPC errors
            return self._handle_grpc_error(e, "cancel_convictions")

        except Exception as e:
            logger.error(f"Unexpected error in cancel_convictions: {e}")
            return {
                "success": False,
                "error": f"Exchange communication error: {str(e)}",
                "results": []
            }

    def _handle_grpc_error(self, error: grpc.aio.AioRpcError, operation: str) -> Dict[str, Any]:
        """Handle gRPC errors for all operations"""
        status_code = error.code()
        if status_code == grpc.StatusCode.UNAVAILABLE:
            logger.error(f"Exchange unavailable during {operation}: {error.details()}")
            return {
                "success": False,
                "error": "Exchange service unavailable, please try again later",
                "results": []
            }
        elif status_code == grpc.StatusCode.DEADLINE_EXCEEDED:
            logger.error(f"Exchange request timed out during {operation}: {error.details()}")
            return {
                "success": False,
                "error": "Exchange service timed out, please try again",
                "results": []
            }
        else:
            logger.error(f"gRPC error during {operation} ({status_code}): {error.details()}")
            return {
                "success": False,
                "error": f"Communication error: {error.details()}",
                "results": []
            }
