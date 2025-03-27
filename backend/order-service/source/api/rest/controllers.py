import logging
import json
import time
from aiohttp import web
from typing import Dict, Any, Optional, Tuple

from source.utils.validation import ValidationError, validate_required_fields, validate_numeric_field, validate_enum_field
from source.models.enums import OrderSide, OrderType
from source.models.order import Order
from source.core.order_manager import OrderManager
from source.utils.metrics import track_order_submission_latency

logger = logging.getLogger('rest_controllers')

def get_token(request):
    """Extract token from request headers or query parameters"""
    auth_header = request.headers.get('Authorization')

    if auth_header and auth_header.startswith('Bearer '):
        return auth_header[7:]

    # Try query parameter
    return request.query.get('token')

class OrderController:
    """Controller for order-related REST endpoints"""
    
    def __init__(self, order_manager: OrderManager):
        """Initialize controller with order manager"""
        self.order_manager = order_manager
    
    async def submit_order(self, request: web.Request) -> web.Response:
        """Handle order submission"""
        try:
            # Start metrics timer
            start_time = time.time()
            
            # Extract token
            token = get_token(request)

            if not token:
                return web.json_response({
                    "success": False,
                    "error": "Authentication token is required"
                }, status=401)

            # Parse request body
            try:
                data = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON in request body"
                }, status=400)

            # Validate request data
            try:
                # Required fields
                validate_required_fields(data, ['sessionId', 'symbol', 'side', 'quantity', 'type'])
                
                # Numeric fields
                validate_numeric_field(data, 'quantity', min_value=0.00001)
                if 'price' in data:
                    validate_numeric_field(data, 'price', min_value=0)
                
                # Enum fields
                validate_enum_field(data, 'side', OrderSide)
                validate_enum_field(data, 'type', OrderType)
            except ValidationError as e:
                return web.json_response({
                    "success": False,
                    "error": str(e),
                    "field": e.field
                }, status=400)

            # Submit order
            result = await self.order_manager.submit_order(data, token)

            # Record metrics
            elapsed_seconds = time.time() - start_time
            track_order_submission_latency(data.get('type', 'UNKNOWN'), result.get('success', False), elapsed_seconds)

            # Determine status code
            status_code = 200 if result.get('success') else 400
            
            return web.json_response(result, status=status_code)

        except Exception as e:
            logger.error(f"Error handling order submission: {e}")
            return web.json_response({
                "success": False,
                "error": "Server error processing order"
            }, status=500)

    async def cancel_order(self, request: web.Request) -> web.Response:
        """Handle order cancellation"""
        try:
            # Extract token
            token = get_token(request)

            if not token:
                return web.json_response({
                    "success": False,
                    "error": "Authentication token is required"
                }, status=401)

            # Parse request body
            try:
                data = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON in request body"
                }, status=400)

            # Validate required fields
            try:
                validate_required_fields(data, ['orderId', 'sessionId'])
            except ValidationError as e:
                return web.json_response({
                    "success": False,
                    "error": str(e)
                }, status=400)

            # Cancel order
            result = await self.order_manager.cancel_order(
                data['orderId'], data['sessionId'], token
            )

            # Determine status code
            status_code = 200 if result.get('success') else 400
            
            return web.json_response(result, status=status_code)

        except Exception as e:
            logger.error(f"Error handling order cancellation: {e}")
            return web.json_response({
                "success": False,
                "error": "Server error processing cancellation"
            }, status=500)

    async def get_order_status(self, request: web.Request) -> web.Response:
        """Handle order status query"""
        try:
            # Extract token
            token = get_token(request)

            if not token:
                return web.json_response({
                    "success": False,
                    "error": "Authentication token is required"
                }, status=401)

            # Get query parameters
            order_id = request.query.get('orderId')
            session_id = request.query.get('sessionId')

            if not order_id or not session_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required query parameters: orderId and sessionId"
                }, status=400)

            # Get order status
            result = await self.order_manager.get_order_status(order_id, session_id, token)

            # Determine status code
            status_code = 200 if result.get('success') else 400
            
            return web.json_response(result, status=status_code)

        except Exception as e:
            logger.error(f"Error handling order status query: {e}")
            return web.json_response({
                "success": False,
                "error": "Server error processing status query"
            }, status=500)

    async def get_user_orders(self, request: web.Request) -> web.Response:
        """Handle user orders query"""
        try:
            # Extract token
            token = get_token(request)

            if not token:
                return web.json_response({
                    "success": False,
                    "error": "Authentication token is required"
                }, status=401)

            # Get pagination parameters
            try:
                limit = int(request.query.get('limit', '50'))
                offset = int(request.query.get('offset', '0'))
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid pagination parameters"
                }, status=400)

            # Limit maximum results
            if limit > 100:
                limit = 100

            # Get user orders
            result = await self.order_manager.get_user_orders(token, limit, offset)

            return web.json_response(result)

        except Exception as e:
            logger.error(f"Error handling user orders query: {e}")
            return web.json_response({
                "success": False,
                "error": "Server error processing orders query"
            }, status=500)

    async def health_check(self, request: web.Request) -> web.Response:
        """Simple health check endpoint"""
        return web.json_response({
            'status': 'UP',
            'timestamp': int(time.time())
        })

    async def readiness_check(self, request: web.Request) -> web.Response:
        """Readiness check endpoint that verifies database connection"""
        try:
            # Check database connection
            db_ready = await self.order_manager.order_repository.check_connection()

            if db_ready:
                return web.json_response({
                    'status': 'READY',
                    'timestamp': int(time.time()),
                    'checks': {
                        'database': 'UP'
                    }
                })
            else:
                return web.json_response({
                    'status': 'NOT READY',
                    'reason': 'Database is not available',
                    'checks': {
                        'database': 'DOWN'
                    }
                }, status=503)
        except Exception as e:
            logger.error(f"Readiness check failed: {e}")
            return web.json_response({
                'status': 'NOT READY',
                'reason': str(e)
            }, status=503)