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
from source.utils.metrics import Metrics

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
        
        # Initialize metrics
        self.metrics = Metrics()

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
        # First validate the auth token
        auth_result = await self.auth_client.validate_token(token)

        if not auth_result.get('valid', False):
            logger.warning(f"Invalid authentication token")
            return {
                "valid": False,
                "error": auth_result.get('error', 'Invalid authentication token')
            }

        user_id = auth_result.get('user_id')
        
        # Ensure user ID was returned
        if not user_id:
            logger.warning("Auth token valid but no user ID returned")
            return {
                "valid": False,
                "error": "Authentication error: missing user ID"
            }

        # Check session using session service
        session_result = await self.session_client.get_session_info(session_id, token)
        
        if not session_result.get('success', False):
            logger.warning(f"Session {session_id} validation failed: {session_result.get('error')}")
            return {
                "valid": False,
                "error": session_result.get('error', 'Session validation failed')
            }
        
        # Get session data from response
        session_data = session_result.get('session', {})
        
        # Verify user owns this session
        session_user_id = session_data.get('user_id')
        if not session_user_id or session_user_id != user_id:
            logger.warning(f"Session {session_id} does not belong to user {user_id}")
            return {
                "valid": False,
                "error": "Session does not belong to this user"
            }
        
        # Get connection quality
        connection_quality = session_data.get('connection_quality', 'good')
        
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
        if not request_id:
            return None

        # Check cache in a thread-safe way
        async with self._cache_lock:
            # Check cache
            request_key = f"{user_id}:{request_id}"
            cached = self.recently_processed.get(request_key)

            if cached:
                # Return cached response for duplicate
                logger.info(f"Returning cached response for duplicate request {request_id}")
                self.metrics.increment_counter("duplicate_request_detected")
                return cached['response']

        # Clean up old cache entries
        await self._cleanup_old_request_ids()

        return None

    async def _cleanup_old_request_ids(self):
        """Clean up old request IDs from cache"""
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

    async def _cache_request_response(self, user_id: str, request_id: str, response: Dict[str, Any]):
        """Cache a response for a request ID"""
        if not request_id:
            return

        async with self._cache_lock:
            request_key = f"{user_id}:{request_id}"
            self.recently_processed[request_key] = {
                'timestamp': time.time(),
                'response': response
            }

    async def submit_order(self, order_data: Dict[str, Any], token: str) -> Dict[str, Any]:
        """
        Submit a new order
        
        Args:
            order_data: Order data
            token: Authentication token
            
        Returns:
            Submission result
        """
        # Extract key fields
        session_id = order_data.get('sessionId')
        request_id = order_data.get('requestId')

        # Validate session and authentication
        validation = await self.validate_session(session_id, token)

        if not validation.get('valid'):
            return {
                "success": False,
                "error": validation.get('error', 'Invalid session or token')
            }

        user_id = validation.get('user_id')
        simulator_id = validation.get('simulator_id')
        simulator_endpoint = validation.get('simulator_endpoint')

        # Check for duplicate request
        if request_id:
            cached_response = await self.check_duplicate_request(user_id, request_id)
            if cached_response:
                return cached_response

        # Reject orders if connection quality is poor
        if validation.get('connection_quality') == 'poor':
            logger.warning(f"Rejecting order for user {user_id} due to poor connection quality")
            response = {
                "success": False,
                "error": "Order rejected: Connection quality is too poor for order submission"
            }
            await self._cache_request_response(user_id, request_id, response)
            return response

        # Prepare order parameters
        try:
            symbol = order_data.get('symbol')
            side = order_data.get('side')
            quantity = float(order_data.get('quantity', 0))
            order_type = order_data.get('type')
            price = float(order_data.get('price', 0)) if 'price' in order_data else None

            # Basic validation already handled in controller, but ensure critical values exist
            if not symbol or not side or not order_type or quantity <= 0:
                logger.warning(f"Order validation failed: {order_data}")
                response = {
                    "success": False,
                    "error": "Invalid order parameters"
                }
                await self._cache_request_response(user_id, request_id, response)
                return response

            # For limit orders, price is required
            if order_type == 'LIMIT' and (price is None or price <= 0):
                response = {
                    "success": False,
                    "error": "Limit orders require a valid price greater than zero"
                }
                await self._cache_request_response(user_id, request_id, response)
                return response

        except ValueError:
            response = {
                "success": False,
                "error": "Invalid order parameters: quantity and price must be numeric"
            }
            await self._cache_request_response(user_id, request_id, response)
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

        # Save order to database
        try:
            save_success = await self.order_repository.save_order(order)

            if not save_success:
                logger.error(f"Failed to save order to database")
                response = {
                    "success": False,
                    "error": "Failed to process order",
                    "orderId": order.order_id
                }
                await self._cache_request_response(user_id, request_id, response)
                return response

        except Exception as db_error:
            logger.error(f"Database error saving order: {db_error}")
            response = {
                "success": False,
                "error": "Database error processing order",
                "orderId": order.order_id
            }
            await self._cache_request_response(user_id, request_id, response)
            return response

        # Check if we have an active simulator - if not, return success but don't forward to exchange
        if not simulator_id or not simulator_endpoint:
            logger.info(f"Order {order.order_id} recorded but no active simulator for session {session_id}")
            response = {
                "success": True,
                "orderId": order.order_id,
                "notice": "Order recorded but not sent to simulator as no active simulator exists"
            }
            await self._cache_request_response(user_id, request_id, response)
            return response

        # If we have a simulator, submit order to exchange
        try:
            exchange_result = await self.exchange_client.submit_order(order, simulator_endpoint)

            if not exchange_result.get('success'):
                # Update order status to REJECTED
                order.status = OrderStatus.REJECTED
                order.error_message = exchange_result.get('error')
                order.updated_at = time.time()
                await self.order_repository.save_order(order)

                logger.warning(f"Order {order.order_id} rejected by exchange: {order.error_message}")
                response = {
                    "success": False,
                    "error": exchange_result.get('error'),
                    "orderId": order.order_id
                }
                await self._cache_request_response(user_id, request_id, response)
                return response

            # Update order if exchange assigned a different ID
            if exchange_result.get('order_id') and exchange_result.get('order_id') != order.order_id:
                old_id = order.order_id
                order.order_id = exchange_result.get('order_id')
                order.updated_at = time.time()
                await self.order_repository.save_order(order)
                logger.info(f"Updated order ID from {old_id} to {order.order_id}")

        except Exception as exchange_error:
            logger.error(f"Exchange error processing order: {exchange_error}")
            # Update order status to ERROR
            order.status = OrderStatus.REJECTED
            order.error_message = f"Exchange communication error: {str(exchange_error)}"
            order.updated_at = time.time()
            await self.order_repository.save_order(order)

            response = {
                "success": False,
                "error": f"Exchange error: {str(exchange_error)}",
                "orderId": order.order_id
            }
            await self._cache_request_response(user_id, request_id, response)
            return response

        # Cache successful response
        response = {
            "success": True,
            "orderId": order.order_id
        }
        await self._cache_request_response(user_id, request_id, response)

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
        # Validate session and authentication
        validation = await self.validate_session(session_id, token)

        if not validation.get('valid'):
            return {
                "success": False,
                "error": validation.get('error', 'Invalid session or token')
            }

        user_id = validation.get('user_id')
        simulator_endpoint = validation.get('simulator_endpoint')

        # Get order from database
        try:
            order = await self.order_repository.get_order(order_id)

            if not order:
                logger.warning(f"Order {order_id} not found")
                return {
                    "success": False,
                    "error": "Order not found"
                }

            # Verify order belongs to user
            if order.user_id != user_id:
                logger.warning(f"Order {order_id} does not belong to user {user_id}")
                return {
                    "success": False,
                    "error": "Order does not belong to this user"
                }

            # Check if order can be canceled
            if order.status not in [OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED]:
                logger.warning(f"Cannot cancel order {order_id} in state {order.status}")
                return {
                    "success": False,
                    "error": f"Cannot cancel order in state {order.status}"
                }

        except Exception as db_error:
            logger.error(f"Database error retrieving order: {db_error}")
            return {
                "success": False,
                "error": f"Database error: {str(db_error)}"
            }

        # Check if we have an active simulator - if not, just update the order status
        if not simulator_endpoint:
            # Update order status directly
            order.status = OrderStatus.CANCELED
            order.updated_at = time.time()
            success = await self.order_repository.save_order(order)
            
            if not success:
                return {
                    "success": False,
                    "error": "Failed to update order status"
                }
                
            return {
                "success": True,
                "notice": "Order canceled in database, but not in simulator (no active simulator)"
            }

        # If we have a simulator, cancel order in exchange
        try:
            exchange_result = await self.exchange_client.cancel_order(order, simulator_endpoint)

            if not exchange_result.get('success'):
                logger.warning(f"Failed to cancel order {order_id}: {exchange_result.get('error')}")
                return {
                    "success": False,
                    "error": exchange_result.get('error', 'Failed to cancel order')
                }

            # Update order status in database
            order.status = OrderStatus.CANCELED
            order.updated_at = time.time()
            await self.order_repository.save_order(order)

            return {
                "success": True
            }

        except Exception as e:
            logger.error(f"Exchange error cancelling order: {e}")
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
        # Validate session and authentication
        validation = await self.validate_session(session_id, token)

        if not validation.get('valid'):
            return {
                "success": False,
                "error": validation.get('error', 'Invalid session or token')
            }

        user_id = validation.get('user_id')
        simulator_endpoint = validation.get('simulator_endpoint')

        # Get order from database
        try:
            order = await self.order_repository.get_order(order_id)

            if not order:
                logger.warning(f"Order {order_id} not found")
                return {
                    "success": False,
                    "error": "Order not found"
                }

            # Verify order belongs to user
            if order.user_id != user_id:
                logger.warning(f"Order {order_id} does not belong to user {user_id}")
                return {
                    "success": False,
                    "error": "Order does not belong to this user"
                }

        except Exception as db_error:
            logger.error(f"Database error retrieving order: {db_error}")
            return {
                "success": False,
                "error": f"Database error: {str(db_error)}"
            }

        # For orders in final state or no simulator, return database status
        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED] or not simulator_endpoint:
            return {
                "success": True,
                "status": order.status.value,
                "filledQuantity": float(order.filled_quantity),
                "avgPrice": float(order.avg_price),
                "errorMessage": order.error_message
            }

        # For active orders with a simulator, get latest status from exchange
        try:
            exchange_result = await self.exchange_client.get_order_status(order, simulator_endpoint)

            if not exchange_result.get('success'):
                logger.warning(f"Failed to get order status from exchange: {exchange_result.get('error')}")
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

            if (status != order.status or
                filled_quantity != order.filled_quantity or
                avg_price != order.avg_price):
                # Update order
                order.status = status
                order.filled_quantity = filled_quantity
                order.avg_price = avg_price
                order.updated_at = time.time()
                await self.order_repository.save_order(order)

            return {
                "success": True,
                "status": status.value if hasattr(status, 'value') else status,
                "filledQuantity": float(filled_quantity),
                "avgPrice": float(avg_price),
                "errorMessage": exchange_result.get('error_message')
            }

        except Exception as e:
            logger.error(f"Error getting order status: {e}")
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
        # Validate token
        auth_result = await self.auth_client.validate_token(token)

        if not auth_result.get('valid', False):
            return {
                "success": False,
                "error": "Invalid authentication token"
            }

        user_id = auth_result.get('user_id')
        
        # Ensure user ID was returned
        if not user_id:
            return {
                "success": False,
                "error": "Authentication error: missing user ID"
            }

        try:
            orders = await self.order_repository.get_user_orders(user_id, limit, offset)

            return {
                "success": True,
                "orders": [order.to_dict() for order in orders],
                "count": len(orders),
                "limit": limit,
                "offset": offset
            }
        except Exception as e:
            logger.error(f"Error getting user orders: {e}")
            return {
                "success": False,
                "error": f"Database error: {str(e)}"
            }