# source/core/order_manager.py
import logging
import time
import uuid
import asyncio
from typing import Dict, Any, Optional, List

from source.models.order import Order, OrderStatus
from source.api.auth_client import AuthClient
from source.core.exchange_client import ExchangeClient
from source.db.order_store import OrderStore

logger = logging.getLogger('order_manager')


class OrderManager:
    """Manager for handling order operations"""

    def __init__(self, order_store: OrderStore, auth_client: AuthClient,
                 exchange_client: ExchangeClient, redis_client):
        self.order_store = order_store
        self.auth_client = auth_client
        self.exchange_client = exchange_client
        self.redis = redis_client

        # Track request IDs to detect duplicates
        self.recently_processed = {}
        self._cache_lock = asyncio.Lock()  # For thread-safe cache operations

    async def validate_session(self, session_id: str, token: str) -> Dict[str, Any]:
        """Validate session and authentication token"""
        # First validate the auth token
        auth_result = await self.auth_client.validate_token(token)

        if not auth_result.get('valid', False):
            logger.warning(f"Invalid authentication token")
            return {
                "valid": False,
                "error": auth_result.get('error', 'Invalid authentication token')
            }

        user_id = auth_result.get('userId')

        # Check if session exists in Redis
        try:
            session_exists = await self.redis.exists(f"session:{session_id}")

            if not session_exists:
                logger.warning(f"Session {session_id} not found")
                return {
                    "valid": False,
                    "error": "Session not found"
                }

            # Check if session belongs to user
            session_user_id = await self.redis.get(f"session:{session_id}:user_id")

            if not session_user_id or session_user_id != user_id:
                logger.warning(f"Session {session_id} does not belong to user {user_id}")
                return {
                    "valid": False,
                    "error": "Session does not belong to this user"
                }

            # Check connection quality
            connection_quality = await self.redis.get(f"connection:{session_id}:quality")

            return {
                "valid": True,
                "user_id": user_id,
                "connection_quality": connection_quality.decode() if connection_quality else "good"
            }
        except Exception as e:
            logger.error(f"Error validating session: {e}")
            return {
                "valid": False,
                "error": f"Session validation error: {str(e)}"
            }

    async def check_duplicate_request(self, user_id: str, request_id: str) -> Optional[Dict[str, Any]]:
        """Check if this is a duplicate request and return cached response if it is"""
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
        """Submit a new order"""
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

        # Validate order parameters
        try:
            symbol = order_data.get('symbol')
            side = order_data.get('side')
            quantity = float(order_data.get('quantity', 0))
            order_type = order_data.get('type')
            price = float(order_data.get('price', 0)) if 'price' in order_data else None

            # Basic validation
            if not symbol or not side or not order_type:
                response = {
                    "success": False,
                    "error": "Missing required order parameters: symbol, side, and type are required"
                }
                await self._cache_request_response(user_id, request_id, response)
                return response

            if quantity <= 0:
                response = {
                    "success": False,
                    "error": "Order quantity must be greater than zero"
                }
                await self._cache_request_response(user_id, request_id, response)
                return response

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

        # Create order object
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
            updated_at=time.time()
        )

        # Save order to database
        try:
            save_success = await self.order_store.save_order(order)

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

        # Submit order to exchange
        try:
            exchange_result = await self.exchange_client.submit_order(order)

            if not exchange_result.get('success'):
                # Update order status to REJECTED
                order.status = OrderStatus.REJECTED
                order.error_message = exchange_result.get('error')
                order.updated_at = time.time()
                await self.order_store.save_order(order)

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
                await self.order_store.save_order(order)
                logger.info(f"Updated order ID from {old_id} to {order.order_id}")

        except Exception as exchange_error:
            logger.error(f"Exchange error processing order: {exchange_error}")
            # Update order status to ERROR
            order.status = OrderStatus.REJECTED
            order.error_message = f"Exchange communication error: {str(exchange_error)}"
            order.updated_at = time.time()
            await self.order_store.save_order(order)

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
        """Cancel an existing order"""
        # Validate session and authentication
        validation = await self.validate_session(session_id, token)

        if not validation.get('valid'):
            return {
                "success": False,
                "error": validation.get('error', 'Invalid session or token')
            }

        user_id = validation.get('user_id')

        # Get order from database
        try:
            order = await self.order_store.get_order(order_id)

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

        # Cancel order in exchange
        try:
            exchange_result = await self.exchange_client.cancel_order(order)

            if not exchange_result.get('success'):
                logger.warning(f"Failed to cancel order {order_id}: {exchange_result.get('error')}")
                return {
                    "success": False,
                    "error": exchange_result.get('error', 'Failed to cancel order')
                }

            # Update order status in database
            order.status = OrderStatus.CANCELED
            order.updated_at = time.time()
            await self.order_store.save_order(order)

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
        """Get status of an existing order"""
        # Validate session and authentication
        validation = await self.validate_session(session_id, token)

        if not validation.get('valid'):
            return {
                "success": False,
                "error": validation.get('error', 'Invalid session or token')
            }

        user_id = validation.get('user_id')

        # Get order from database
        try:
            order = await self.order_store.get_order(order_id)

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

        # For orders in final state, return database status
        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED]:
            return {
                "success": True,
                "status": order.status.value if hasattr(order.status, 'value') else order.status,
                "filledQuantity": float(order.filled_quantity),
                "avgPrice": float(order.avg_price),
                "errorMessage": order.error_message
            }

        # For active orders, get latest status from exchange
        try:
            exchange_result = await self.exchange_client.get_order_status(order)

            if not exchange_result.get('success'):
                logger.warning(f"Failed to get order status from exchange: {exchange_result.get('error')}")
                # Fall back to database status
                return {
                    "success": True,
                    "status": order.status.value if hasattr(order.status, 'value') else order.status,
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
                await self.order_store.save_order(order)

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
                "status": order.status.value if hasattr(order.status, 'value') else order.status,
                "filledQuantity": float(order.filled_quantity),
                "avgPrice": float(order.avg_price),
                "errorMessage": f"Exchange error: {str(e)}"
            }

    async def get_user_orders(self, user_id: str, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Get orders for a user"""
        try:
            orders = await self.order_store.get_user_orders(user_id, limit, offset)

            return {
                "success": True,
                "orders": [order.to_dict() for order in orders],
                "count": len(orders)
            }
        except Exception as e:
            logger.error(f"Error getting user orders: {e}")
            return {
                "success": False,
                "error": f"Database error: {str(e)}"
            }
