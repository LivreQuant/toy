import logging
import time
import uuid
import asyncio
from typing import Dict, Any, Optional, List

from source.models.order import Order
from source.models.enums import OrderStatus
from source.db.order_repository import OrderRepository
from source.api.clients.auth_client import AuthClient
from source.api.clients.session_client import SessionClient
from source.api.clients.exchange_client import ExchangeClient
from source.utils.metrics import (
    track_order_created, track_order_submitted, track_order_submission_latency,
    track_order_status_change, track_user_order, track_session_order
)
from opentelemetry import trace

from source.utils.tracing import optional_trace_span

logger = logging.getLogger('order_manager')

class OrderManager:
    """Manager for handling order operations"""

    def __init__(
        self, 
        order_repository: OrderRepository, 
        auth_client: AuthClient,
        session_client: SessionClient,
        exchange_client: ExchangeClient
    ):
        """
        Initialize the order manager
        
        Args:
            order_repository: Repository for order data
            auth_client: Client for auth service
            session_client: Client for session service
            exchange_client: Client for exchange service
        """
        self.order_repository = order_repository
        self.auth_client = auth_client
        self.session_client = session_client
        self.exchange_client = exchange_client
        self.tracer = trace.get_tracer("order_manager")

        # Track request IDs to detect duplicates
        self.recently_processed = {}
        self._cache_lock = asyncio.Lock()  # For thread-safe cache operations

    async def validate_session(self, session_id: str, token: str) -> Dict[str, Any]:
        """
        Validate session and authentication token
        
        Args:
            session_id: The session ID
            token: Authentication token
            
        Returns:
            Validation result
        """
        with optional_trace_span(self.tracer, "validate_session") as span:
            span.set_attribute("session_id", session_id)

            # First validate the auth token
            auth_result = await self.auth_client.validate_token(token)

            if not auth_result.get('valid', False):
                logger.warning(f"Invalid authentication token")
                span.set_attribute("auth_valid", False)
                return {
                    "valid": False,
                    "error": auth_result.get('error', 'Invalid authentication token')
                }

            user_id = auth_result.get('user_id')
            span.set_attribute("auth_valid", True)
            span.set_attribute("user_id", user_id)

            # Ensure user ID was returned
            if not user_id:
                logger.warning("Auth token valid but no user ID returned")
                span.set_attribute("error", "Missing user ID")
                return {
                    "valid": False,
                    "error": "Authentication error: missing user ID"
                }

            # Check session using session service
            session_result = await self.session_client.get_session_info(session_id, token)

            if not session_result.get('success', False):
                logger.warning(f"Session {session_id} validation failed: {session_result.get('error')}")
                span.set_attribute("session_valid", False)
                span.set_attribute("error", session_result.get('error'))
                return {
                    "valid": False,
                    "error": session_result.get('error', 'Session validation failed')
                }

            # Get session data from response
            session_data = session_result.get('session', {})
            span.set_attribute("session_valid", True)

            # Verify user owns this session
            session_user_id = session_data.get('user_id')
            if not session_user_id or session_user_id != user_id:
                logger.warning(f"Session {session_id} does not belong to user {user_id}")
                span.set_attribute("session_owner_valid", False)
                span.set_attribute("error", "Session ownership mismatch")
                return {
                    "valid": False,
                    "error": "Session does not belong to this user"
                }

            span.set_attribute("session_owner_valid", True)

            # Get connection quality
            connection_quality = session_data.get('connection_quality', 'good')
            span.set_attribute("connection_quality", connection_quality)
            span.set_attribute("simulator_id", simulator_id if simulator_id else "none")
            span.set_attribute("simulator_endpoint", simulator_endpoint if simulator_endpoint else "none")

            return {
                "valid": True,
                "user_id": user_id,
                "connection_quality": connection_quality,
                "simulator_id": session_data.get('simulator_id'),
                "simulator_endpoint": session_data.get('simulator_endpoint')
            }

    async def check_duplicate_request(self, user_id: str, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Check if this is a duplicate request and return cached response if it is
        
        Args:
            user_id: User ID
            request_id: Request ID
            
        Returns:
            Cached response if duplicate, None otherwise
        """
        with optional_trace_span(self.tracer, "check_duplicate_request") as span:
            span.set_attribute("user_id", user_id)
            span.set_attribute("request_id", request_id if request_id else "none")

            if not request_id:
                span.set_attribute("is_duplicate", False)
                return None

            # Check cache in a thread-safe way
            async with self._cache_lock:
                # Check cache
                request_key = f"{user_id}:{request_id}"
                cached = self.recently_processed.get(request_key)

                if cached:
                    # Return cached response for duplicate
                    logger.info(f"Returning cached response for duplicate request {request_id}")
                    span.set_attribute("is_duplicate", True)
                    return cached['response']

            # Clean up old cache entries
            await self._cleanup_old_request_ids()
            span.set_attribute("is_duplicate", False)
            return None

    async def _cleanup_old_request_ids(self):
        """Clean up old request IDs from cache"""
        with optional_trace_span(self.tracer, "_cleanup_old_request_ids") as span:
            async with self._cache_lock:
                current_time = time.time()
                expiry = 300  # 5 minutes

                # Remove entries older than expiry time
                keys_to_remove = []
                for key, entry in self.recently_processed.items():
                    if current_time - entry['timestamp'] > expiry:
                        keys_to_remove.append(key)

                for key in keys_to_remove:
                    del self.recently_processed[key]

                span.set_attribute("keys_removed", len(keys_to_remove))
                span.set_attribute("remaining_keys", len(self.recently_processed))

    async def _cache_request_response(self, user_id: str, request_id: str, response: Dict[str, Any]):
        """Cache a response for a request ID"""
        with optional_trace_span(self.tracer, "_cache_request_response") as span:
            span.set_attribute("user_id", user_id)
            span.set_attribute("request_id", request_id if request_id else "none")

            if not request_id:
                return

            async with self._cache_lock:
                request_key = f"{user_id}:{request_id}"
                self.recently_processed[request_key] = {
                    'timestamp': time.time(),
                    'response': response
                }
                span.set_attribute("cache_size", len(self.recently_processed))


    async def submit_order(self, order_data: Dict[str, Any], token: str) -> Dict[str, Any]:
        """
        Submit a new order
        
        Args:
            order_data: Order data
            token: Authentication token
            
        Returns:
            Submission result
        """
        with optional_trace_span(self.tracer, "submit_order") as span:
            start_time = time.time()

            # Extract key fields
            session_id = order_data.get('sessionId')
            request_id = order_data.get('requestId')

            span.set_attribute("session_id", session_id)
            span.set_attribute("request_id", request_id if request_id else "none")

            # Validate session and authentication
            validation = await self.validate_session(session_id, token)
            span.set_attribute("session_valid", validation.get('valid', False))

            if not validation.get('valid'):
                error_msg = validation.get('error', 'Invalid session or token')
                span.set_attribute("error", error_msg)

                # Record submission failure
                duration = time.time() - start_time
                track_order_submission_latency(order_data.get('type', 'UNKNOWN'), False, duration)

                return {
                    "success": False,
                    "error": error_msg
                }

            user_id = validation.get('user_id')
            simulator_id = validation.get('simulator_id')
            simulator_endpoint = validation.get('simulator_endpoint')

            span.set_attribute("user_id", user_id)
            span.set_attribute("simulator_id", simulator_id if simulator_id else "none")

            # Check for duplicate request
            if request_id:
                cached_response = await self.check_duplicate_request(user_id, request_id)
                if cached_response:
                    span.set_attribute("duplicate_request", True)
                    return cached_response

            # Reject orders if connection quality is poor
            if validation.get('connection_quality') == 'poor':
                logger.warning(f"Rejecting order for user {user_id} due to poor connection quality")
                span.set_attribute("connection_quality", "poor")
                span.set_attribute("error", "Poor connection quality")

                response = {
                    "success": False,
                    "error": "Order rejected: Connection quality is too poor for order submission"
                }
                await self._cache_request_response(user_id, request_id, response)

                # Record submission failure
                duration = time.time() - start_time
                track_order_submission_latency(order_data.get('type', 'UNKNOWN'), False, duration)

                return response

            # Prepare order parameters
            try:
                symbol = order_data.get('symbol')
                side = order_data.get('side')
                quantity = float(order_data.get('quantity', 0))
                order_type = order_data.get('type')
                price = float(order_data.get('price', 0)) if 'price' in order_data else None

                span.set_attribute("symbol", symbol)
                span.set_attribute("side", side)
                span.set_attribute("quantity", quantity)
                span.set_attribute("order_type", order_type)
                span.set_attribute("price", price if price is not None else 0)

                # Basic validation already handled in controller, but ensure critical values exist
                if not symbol or not side or not order_type or quantity <= 0:
                    logger.warning(f"Order validation failed: {order_data}")
                    span.set_attribute("error", "Invalid order parameters")

                    response = {
                        "success": False,
                        "error": "Invalid order parameters"
                    }
                    await self._cache_request_response(user_id, request_id, response)

                    # Record submission failure
                    duration = time.time() - start_time
                    track_order_submission_latency(order_type if order_type else "UNKNOWN", False, duration)

                    return response

                # For limit orders, price is required
                if order_type == 'LIMIT' and (price is None or price <= 0):
                    span.set_attribute("error", "Missing price for limit order")

                    response = {
                        "success": False,
                        "error": "Limit orders require a valid price greater than zero"
                    }
                    await self._cache_request_response(user_id, request_id, response)

                    # Record submission failure
                    duration = time.time() - start_time
                    track_order_submission_latency("LIMIT", False, duration)

                    return response

            except ValueError:
                span.record_exception(e)
                span.set_attribute("error", "Invalid numeric values")

                response = {
                    "success": False,
                    "error": "Invalid order parameters: quantity and price must be numeric"
                }
                await self._cache_request_response(user_id, request_id, response)

                # Record submission failure
                duration = time.time() - start_time
                track_order_submission_latency(order_data.get('type', 'UNKNOWN'), False, duration)

                return response

            # Create order object - include simulator_id even if it's None
            order = Order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                price=price,
                user_id=user_id,
                session_id=session_id,
                request_id=request_id,
                order_id=str(uuid.uuid4()),  # Generate new order ID
                created_at=time.time(),
                updated_at=time.time(),
                simulator_id=simulator_id
            )

            span.set_attribute("order_id", order.order_id)

            # Track order creation metrics
            track_order_created(order_type, symbol, side)
            track_user_order(user_id)
            track_session_order(session_id)

            # Save order to database
            try:
                save_success = await self.order_repository.save_order(order)

                if not save_success:
                    logger.error(f"Failed to save order to database")
                    span.set_attribute("db_save_success", False)
                    span.set_attribute("error", "Database save failed")

                    response = {
                        "success": False,
                        "error": "Failed to process order",
                        "orderId": order.order_id
                    }
                    await self._cache_request_response(user_id, request_id, response)

                    # Record submission failure
                    duration = time.time() - start_time
                    track_order_submission_latency(order_type, False, duration)

                    return response

                span.set_attribute("db_save_success", True)

            except Exception as db_error:
                logger.error(f"Database error saving order: {db_error}")
                span.record_exception(db_error)
                span.set_attribute("error", str(db_error))

                response = {
                    "success": False,
                    "error": "Database error processing order",
                    "orderId": order.order_id
                }
                await self._cache_request_response(user_id, request_id, response)

                # Record submission failure
                duration = time.time() - start_time
                track_order_submission_latency(order_type, False, duration)

                return response

            # Check if we have an active simulator - if not, return success but don't forward to exchange
            if not simulator_id or not simulator_endpoint:
                logger.info(f"Order {order.order_id} recorded but no active simulator for session {session_id}")
                span.set_attribute("has_simulator", False)

                response = {
                    "success": True,
                    "orderId": order.order_id,
                    "notice": "Order recorded but not sent to simulator as no active simulator exists"
                }
                await self._cache_request_response(user_id, request_id, response)

                # Record submission success (but not submitted to exchange)
                duration = time.time() - start_time
                track_order_submission_latency(order_type, True, duration)

                return response

            # If we have a simulator, submit order to exchange
            try:
                span.set_attribute("has_simulator", True)

                # Attempt to submit to exchange
                exchange_result = await self.exchange_client.submit_order(order, simulator_endpoint)
                span.set_attribute("exchange_success", exchange_result.get('success', False))

                if not exchange_result.get('success'):
                    # Update order status to REJECTED
                    order.status = OrderStatus.REJECTED
                    order.error_message = exchange_result.get('error')
                    order.updated_at = time.time()
                    await self.order_repository.save_order(order)

                    # Track status change
                    track_order_status_change('NEW', 'REJECTED')

                    span.set_attribute("error", exchange_result.get('error'))

                    logger.warning(f"Order {order.order_id} rejected by exchange: {order.error_message}")
                    response = {
                        "success": False,
                        "error": exchange_result.get('error'),
                        "orderId": order.order_id
                    }
                    await self._cache_request_response(user_id, request_id, response)

                    # Record submission failure
                    duration = time.time() - start_time
                    track_order_submission_latency(order_type, False, duration)

                    return response

                # Update order if exchange assigned a different ID
                if exchange_result.get('order_id') and exchange_result.get('order_id') != order.order_id:
                    old_id = order.order_id
                    order.order_id = exchange_result.get('order_id')
                    order.updated_at = time.time()
                    await self.order_repository.save_order(order)
                    logger.info(f"Updated order ID from {old_id} to {order.order_id}")
                    span.set_attribute("order_id_updated", True)
                    span.set_attribute("new_order_id", order.order_id)

                # Track order submitted to exchange
                track_order_submitted(order_type, symbol, side)

            except Exception as exchange_error:
                logger.error(f"Exchange error processing order: {exchange_error}")
                span.record_exception(exchange_error)
                span.set_attribute("error", str(exchange_error))

                # Update order status to ERROR
                order.status = OrderStatus.REJECTED
                order.error_message = f"Exchange communication error: {str(exchange_error)}"
                order.updated_at = time.time()
                await self.order_repository.save_order(order)

                # Track status change
                track_order_status_change('NEW', 'REJECTED')

                response = {
                    "success": False,
                    "error": f"Exchange error: {str(exchange_error)}",
                    "orderId": order.order_id
                }
                await self._cache_request_response(user_id, request_id, response)

                # Record submission failure
                duration = time.time() - start_time
                track_order_submission_latency(order_type, False, duration)

                return response

            # Record submission success
            duration = time.time() - start_time
            track_order_submission_latency(order_type, True, duration)

            # Cache successful response
            response = {
                "success": True,
                "orderId": order.order_id
            }
            await self._cache_request_response(user_id, request_id, response)
            span.set_attribute("success", True)

            return response

    async def cancel_order(self, order_id: str, session_id: str, token: str) -> Dict[str, Any]:
        """
        Cancel an existing order
        
        Args:
            order_id: Order ID to cancel
            session_id: Session ID
            token: Authentication token
            
        Returns:
            Cancellation result
        """
        with optional_trace_span(self.tracer, "cancel_order") as span:
            span.set_attribute("order_id", order_id)
            span.set_attribute("session_id", session_id)

            # Validate session and authentication
            validation = await self.validate_session(session_id, token)
            span.set_attribute("session_valid", validation.get('valid', False))

            if not validation.get('valid'):
                error_msg = validation.get('error', 'Invalid session or token')
                span.set_attribute("error", error_msg)
                return {
                    "success": False,
                    "error": error_msg
                }

            user_id = validation.get('user_id')
            simulator_endpoint = validation.get('simulator_endpoint')

            span.set_attribute("user_id", user_id)
            span.set_attribute("has_simulator", simulator_endpoint is not None)

            # Get order from database
            try:
                order = await self.order_repository.get_order(order_id)
                span.set_attribute("order_found", order is not None)

                if not order:
                    logger.warning(f"Order {order_id} not found")
                    span.set_attribute("error", "Order not found")
                    return {
                        "success": False,
                        "error": "Order not found"
                    }

                # Verify order belongs to user
                if order.user_id != user_id:
                    logger.warning(f"Order {order_id} does not belong to user {user_id}")
                    span.set_attribute("error", "Order does not belong to this user")
                    return {
                        "success": False,
                        "error": "Order does not belong to this user"
                    }

                span.set_attribute("order_status", order.status.value)

                # Check if order can be canceled
                if order.status not in [OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED]:
                    logger.warning(f"Cannot cancel order {order_id} in state {order.status}")
                    span.set_attribute("error", f"Order in state {order.status} cannot be cancelled")
                    return {
                        "success": False,
                        "error": f"Cannot cancel order in state {order.status}"
                    }

            except Exception as db_error:
                logger.error(f"Database error retrieving order: {db_error}")
                span.record_exception(db_error)
                span.set_attribute("error", str(db_error))
                return {
                    "success": False,
                    "error": f"Database error: {str(db_error)}"
                }

            # Check if we have an active simulator - if not, just update the order status
            if not simulator_endpoint:
                # Update order status directly
                prev_status = order.status.value
                order.status = OrderStatus.CANCELED
                order.updated_at = time.time()
                success = await self.order_repository.save_order(order)

                # Track status change
                track_order_status_change(prev_status, 'CANCELED')

                span.set_attribute("status_updated", success)

                if not success:
                    span.set_attribute("error", "Failed to update order status")
                    return {
                        "success": False,
                        "error": "Failed to update order status"
                    }

                span.set_attribute("success", True)
                return {
                    "success": True,
                    "notice": "Order canceled in database, but not in simulator (no active simulator)"
                }

            # If we have a simulator, cancel order in exchange
            try:
                exchange_result = await self.exchange_client.cancel_order(order, simulator_endpoint)
                span.set_attribute("exchange_success", exchange_result.get('success', False))

                if not exchange_result.get('success'):
                    logger.warning(f"Failed to cancel order {order_id}: {exchange_result.get('error')}")
                    span.set_attribute("error", exchange_result.get('error'))
                    return {
                        "success": False,
                        "error": exchange_result.get('error', 'Failed to cancel order')
                    }

                # Update order status in database
                prev_status = order.status.value
                order.status = OrderStatus.CANCELED
                order.updated_at = time.time()
                await self.order_repository.save_order(order)

                # Track status change
                track_order_status_change(prev_status, 'CANCELED')

                span.set_attribute("success", True)

                return {
                    "success": True
                }

            except Exception as e:
                logger.error(f"Exchange error cancelling order: {e}")
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return {
                    "success": False,
                    "error": f"Exchange error: {str(e)}"
                }

    async def get_order_status(self, order_id: str, session_id: str, token: str) -> Dict[str, Any]:
        """
        Get status of an existing order
        
        Args:
            order_id: Order ID
            session_id: Session ID
            token: Authentication token
            
        Returns:
            Order status information
        """
        with optional_trace_span(self.tracer, "get_order_status") as span:
            span.set_attribute("order_id", order_id)
            span.set_attribute("session_id", session_id)

            # Validate session and authentication
            validation = await self.validate_session(session_id, token)
            span.set_attribute("session_valid", validation.get('valid', False))

            if not validation.get('valid'):
                error_msg = validation.get('error', 'Invalid session or token')
                span.set_attribute("error", error_msg)
                return {
                    "success": False,
                    "error": error_msg
                }

            user_id = validation.get('user_id')
            simulator_endpoint = validation.get('simulator_endpoint')

            span.set_attribute("user_id", user_id)
            span.set_attribute("has_simulator", simulator_endpoint is not None)

            # Get order from database
            try:
                order = await self.order_repository.get_order(order_id)
                span.set_attribute("order_found", order is not None)

                if not order:
                    logger.warning(f"Order {order_id} not found")
                    span.set_attribute("error", "Order not found")
                    return {
                        "success": False,
                        "error": "Order not found"
                    }

                # Verify order belongs to user
                if order.user_id != user_id:
                    logger.warning(f"Order {order_id} does not belong to user {user_id}")
                    span.set_attribute("error", "Order does not belong to this user")
                    return {
                        "success": False,
                        "error": "Order does not belong to this user"
                    }

                span.set_attribute("order_status", order.status.value)

            except Exception as db_error:
                logger.error(f"Database error retrieving order: {db_error}")
                span.record_exception(db_error)
                span.set_attribute("error", str(db_error))
                return {
                    "success": False,
                    "error": f"Database error: {str(db_error)}"
                }

            # For orders in final state or no simulator, return database status
            if order.status in [OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED] or not simulator_endpoint:
                span.set_attribute("using_db_status", True)
                span.set_attribute("success", True)
                return {
                    "success": True,
                    "status": order.status.value,
                    "filledQuantity": float(order.filled_quantity),
                    "avgPrice": float(order.avg_price),
                    "errorMessage": order.error_message
                }

            # For active orders with a simulator, get latest status from exchange
            try:
                span.set_attribute("using_db_status", False)

                exchange_result = await self.exchange_client.get_order_status(order, simulator_endpoint)
                span.set_attribute("exchange_success", exchange_result.get('success', False))

                if not exchange_result.get('success'):
                    logger.warning(f"Failed to get order status from exchange: {exchange_result.get('error')}")
                    span.set_attribute("error", exchange_result.get('error'))
                    # Fall back to database status
                    return {
                        "success": True,
                        "status": order.status.value,
                        "filledQuantity": float(order.filled_quantity),
                        "avgPrice": float(order.avg_price),
                        "errorMessage": exchange_result.get('error')
                    }

                # Update order in database if status changed
                status = exchange_result.get('status')
                filled_quantity = exchange_result.get('filled_quantity')
                avg_price = exchange_result.get('avg_price')

                span.set_attribute("exchange_status", status.value if hasattr(status, 'value') else str(status))
                span.set_attribute("filled_quantity", filled_quantity)
                span.set_attribute("avg_price", avg_price)

                if (status != order.status or
                    filled_quantity != order.filled_quantity or
                    avg_price != order.avg_price):

                    # Track status change if it changed
                    if status != order.status:
                        track_order_status_change(order.status.value, status.value if hasattr(status, 'value') else str(status))

                    # Update order
                    order.status = status
                    order.filled_quantity = filled_quantity
                    order.avg_price = avg_price
                    order.updated_at = time.time()
                    await self.order_repository.save_order(order)
                    span.set_attribute("order_updated", True)

                span.set_attribute("success", True)
                return {
                    "success": True,
                    "status": status.value if hasattr(status, 'value') else status,
                    "filledQuantity": float(filled_quantity),
                    "avgPrice": float(avg_price),
                    "errorMessage": exchange_result.get('error_message')
                }

            except Exception as e:
                logger.error(f"Error getting order status: {e}")
                span.record_exception(e)
                span.set_attribute("error", str(e))
                # Fall back to database status
                return {
                    "success": True,
                    "status": order.status.value,
                    "filledQuantity": float(order.filled_quantity),
                    "avgPrice": float(order.avg_price),
                    "errorMessage": f"Exchange error: {str(e)}"
                }

    async def get_user_orders(self, token: str, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """
        Get orders for a user
        
        Args:
            token: Authentication token
            limit: Maximum number of orders to return
            offset: Offset for pagination
            
        Returns:
            User orders list
        """
        with optional_trace_span(self.tracer, "get_user_orders") as span:
            span.set_attribute("limit", limit)
            span.set_attribute("offset", offset)

            # Validate token
            auth_result = await self.auth_client.validate_token(token)
            span.set_attribute("auth_valid", auth_result.get('valid', False))

            if not auth_result.get('valid', False):
                span.set_attribute("error", "Invalid authentication token")
                return {
                    "success": False,
                    "error": "Invalid authentication token"
                }

            user_id = auth_result.get('user_id')
            span.set_attribute("user_id", user_id)

            # Ensure user ID was returned
            if not user_id:
                span.set_attribute("error", "Missing user ID")
                return {
                    "success": False,
                    "error": "Authentication error: missing user ID"
                }

            try:
                orders = await self.order_repository.get_user_orders(user_id, limit, offset)
                span.set_attribute("order_count", len(orders))
                span.set_attribute("success", True)

                return {
                    "success": True,
                    "orders": [order.to_dict() for order in orders],
                    "count": len(orders),
                    "limit": limit,
                    "offset": offset
                }
            except Exception as e:
                logger.error(f"Error getting user orders: {e}")
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return {
                    "success": False,
                    "error": f"Database error: {str(e)}"
                }
