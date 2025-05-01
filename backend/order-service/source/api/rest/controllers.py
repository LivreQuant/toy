import logging
import json
import time
from aiohttp import web

from source.core.order_manager import OrderManager

logger = logging.getLogger('rest_controllers')


def get_token(request):
    """Extract token from request headers or query parameters"""
    auth_header = request.headers.get('Authorization')

    if auth_header and auth_header.startswith('Bearer '):
        return auth_header[7:], request.query.get('deviceId')

    # Try query parameter
    return request.query.get('token'), request.query.get('deviceId')


class OrderController:
    """Controller for order-related REST endpoints"""

    def __init__(self, order_manager: OrderManager, state_manager):
        """Initialize controller with order manager and state manager"""
        self.order_manager = order_manager
        self.state_manager = state_manager

    async def _get_user_id_from_token(self, token: str) -> str:
        """Extract user ID from authentication token"""
        try:
            validation_result = await self.order_manager.validation_manager.auth_client.validate_token(token)

            if not validation_result.get('valid', False):
                logger.warning(f"Invalid authentication token")
                return None

            user_id = validation_result.get('user_id')
            if not user_id:
                logger.warning("Auth token valid but no user ID returned")
                return None

            return user_id
        except Exception as e:
            logger.error(f"Error extracting user ID from token: {e}")
            return None

    async def health_check(self, request: web.Request) -> web.Response:
        """Simple health check endpoint"""
        return web.json_response({
            'status': 'UP',
            'timestamp': int(time.time())
        })

    async def readiness_check(self, request: web.Request) -> web.Response:
        """Readiness check endpoint that verifies database connection and service availability"""
        try:
            # Check database connection
            db_ready = await self.order_manager.order_repository.check_connection()

            # Check if the service is already busy with another request
            service_ready = self.state_manager.is_ready()

            if db_ready and service_ready:
                return web.json_response({
                    'status': 'READY',
                    'timestamp': int(time.time()),
                    'checks': {
                        'database': 'UP',
                        'service': 'AVAILABLE'
                    }
                })
            else:
                checks = {
                    'database': 'UP' if db_ready else 'DOWN',
                    'service': 'AVAILABLE' if service_ready else 'BUSY'
                }

                reasons = []
                if not db_ready:
                    reasons.append('Database is not available')
                if not service_ready:
                    reasons.append('Service is currently processing a request')

                return web.json_response({
                    'status': 'NOT READY',
                    'reason': '; '.join(reasons),
                    'checks': checks
                }, status=503)
        except Exception as e:
            logger.error(f"Readiness check failed: {e}")
            return web.json_response({
                'status': 'NOT READY',
                'reason': str(e)
            }, status=503)

     
    async def submit_orders(self, request: web.Request) -> web.Response:
        """
        Handle order submission endpoint - Only batch submission is supported
        """
        # Try to acquire the lock first
        acquired = await self.state_manager.acquire()
        if not acquired:
            return web.json_response({
                "success": False,
                "error": "Service is currently busy. Please try again later."
            }, status=503)  # Service Unavailable

        try:
            # Extract token and device ID
            token, device_id = get_token(request)

            if not token:
                return web.json_response({
                    "success": False,
                    "error": "Authentication token is required"
                }, status=401)

            # Get user_id from token
            user_id = await self._get_user_id_from_token(token)
            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Invalid authentication token"
                }, status=401)

            # Validate device ID
            device_valid = await self.order_manager.validation_manager.validate_device_id(device_id)
            if not device_valid:
                return web.json_response({
                    "success": False,
                    "error": "Invalid device ID for this session"
                }, status=400)

            # Parse request body
            try:
                data = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON in request body"
                }, status=400)

            # Extract orders array
            if not isinstance(data, dict) or 'orders' not in data or not isinstance(data['orders'], list):
                return web.json_response({
                    "success": False,
                    "error": "Request must contain an 'orders' array"
                }, status=400)

            orders = data['orders']
            if len(orders) == 0:
                return web.json_response({
                    "success": False,
                    "error": "No orders provided"
                }, status=400)

            if len(orders) > 100:  # Set a reasonable limit
                return web.json_response({
                    "success": False,
                    "error": f"Too many orders. Maximum of 100 allowed per batch."
                }, status=400)

            # Process orders
            result = await self.order_manager.submit_orders(orders, user_id)
            return web.json_response(result)

        except Exception as e:
            logger.error(f"Error handling order submission: {e}")
            return web.json_response({
                "success": False,
                "error": "Server error processing order"
            }, status=500)
        finally:
            # Always release the lock, even if there's an error
            await self.state_manager.release()

    async def cancel_orders(self, request: web.Request) -> web.Response:
        """
        Handle order cancellation endpoint - Only batch cancellation is supported
        """
        # Try to acquire the lock first
        acquired = await self.state_manager.acquire()
        if not acquired:
            return web.json_response({
                "success": False,
                "error": "Service is currently busy. Please try again later."
            }, status=503)  # Service Unavailable
            
        try:
            # Extract token and device ID
            token, device_id = get_token(request)

            if not token:
                return web.json_response({
                    "success": False,
                    "error": "Authentication token is required"
                }, status=401)

            # Get user_id from token
            user_id = await self._get_user_id_from_token(token)
            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Invalid authentication token"
                }, status=401)

            # Validate device ID
            device_valid = await self.order_manager.validation_manager.validate_device_id(device_id)
            if not device_valid:
                return web.json_response({
                    "success": False,
                    "error": "Invalid device ID for this session"
                }, status=400)

            # Parse request body
            try:
                data = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON in request body"
                }, status=400)

            # Extract order_ids array
            if not isinstance(data, dict) or 'orderIds' not in data or not isinstance(data['orderIds'], list):
                return web.json_response({
                    "success": False,
                    "error": "Request must contain an 'orderIds' array"
                }, status=400)

            order_ids = data['orderIds']
            if len(order_ids) == 0:
                return web.json_response({
                    "success": False,
                    "error": "No order IDs provided"
                }, status=400)

            if len(order_ids) > 100:  # Set a reasonable limit
                return web.json_response({
                    "success": False,
                    "error": f"Too many orders. Maximum of 100 cancellations allowed per batch."
                }, status=400)

            # Process cancellations
            result = await self.order_manager.cancel_orders(order_ids, user_id)
            return web.json_response(result)

        except Exception as e:
            logger.error(f"Error handling order cancellation: {e}")
            return web.json_response({
                "success": False,
                "error": "Server error processing cancellation"
            }, status=500)
        finally:
            # Always release the lock, even if there's an error
            await self.state_manager.release()