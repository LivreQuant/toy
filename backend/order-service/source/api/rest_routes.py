# source/api/rest_routes.py
import logging
import json
import aiohttp_cors
from aiohttp import web
import time

logger = logging.getLogger('rest_api')

def setup_rest_app(order_manager):
    """Set up the REST API application with routes and middleware"""
    app = web.Application()
    
    # Add routes
    app.router.add_post('/api/orders/submit', handle_submit_order(order_manager))
    app.router.add_post('/api/orders/cancel', handle_cancel_order(order_manager))
    app.router.add_get('/api/orders/status', handle_get_order_status(order_manager))
    app.router.add_get('/api/orders/user', handle_get_user_orders(order_manager))
    app.router.add_get('/health', handle_health_check)
    app.router.add_get('/readiness', handle_readiness_check(order_manager))
    
    # Set up CORS
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        )
    })
    
    # Apply CORS to all routes
    for route in list(app.router.routes()):
        cors.add(route)
    
    return app

def get_token(request):
    """Extract token from request headers or query parameters"""
    auth_header = request.headers.get('Authorization')
    
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header[7:]
    
    # Try query parameter
    return request.query.get('token')

def handle_submit_order(order_manager):
    """Handle order submission"""
    async def submit_order_handler(request):
        try:
            # Extract token
            token = get_token(request)
            
            if not token:
                return web.json_response({
                    "success": False,
                    "error": "Authentication token is required"
                }, status=401)
            
            # Parse request body
            data = await request.json()
            
            # Validate required fields
            required_fields = ['sessionId', 'symbol', 'side', 'quantity', 'type']
            for field in required_fields:
                if field not in data:
                    return web.json_response({
                        "success": False,
                        "error": f"Missing required field: {field}"
                    }, status=400)
            
            # Submit order
            result = await order_manager.submit_order(data, token)
            
            if not result.get('success'):
                return web.json_response(result, status=400)
            
            return web.json_response(result)
            
        except json.JSONDecodeError:
            return web.json_response({
                "success": False,
                "error": "Invalid JSON in request body"
            }, status=400)
        except Exception as e:
            logger.error(f"Error handling order submission: {e}")
            return web.json_response({
                "success": False,
                "error": "Server error processing order"
            }, status=500)
    
    return submit_order_handler

def handle_cancel_order(order_manager):
    """Handle order cancellation"""
    async def cancel_order_handler(request):
        try:
            # Extract token
            token = get_token(request)
            
            if not token:
                return web.json_response({
                    "success": False,
                    "error": "Authentication token is required"
                }, status=401)
            
            # Parse request body
            data = await request.json()
            
            # Validate required fields
            if 'orderId' not in data or 'sessionId' not in data:
                return web.json_response({
                    "success": False,
                    "error": "Missing required fields: orderId and sessionId"
                }, status=400)
            
            # Cancel order
            result = await order_manager.cancel_order(
                data['orderId'], data['sessionId'], token
            )
            
            if not result.get('success'):
                return web.json_response(result, status=400)
            
            return web.json_response(result)
            
        except json.JSONDecodeError:
            return web.json_response({
                "success": False,
                "error": "Invalid JSON in request body"
            }, status=400)
        except Exception as e:
            logger.error(f"Error handling order cancellation: {e}")
            return web.json_response({
                "success": False,
                "error": "Server error processing cancellation"
            }, status=500)
    
    return cancel_order_handler

def handle_get_order_status(order_manager):
    """Handle order status query"""
    async def get_order_status_handler(request):
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
            result = await order_manager.get_order_status(order_id, session_id, token)
            
            if not result.get('success'):
                return web.json_response(result, status=400)
            
            return web.json_response(result)
            
        except Exception as e:
            logger.error(f"Error handling order status query: {e}")
            return web.json_response({
                "success": False,
                "error": "Server error processing status query"
            }, status=500)
    
    return get_order_status_handler

def handle_get_user_orders(order_manager):
    """Handle user orders query"""
    async def get_user_orders_handler(request):
        try:
            # Extract token
            token = get_token(request)
            
            if not token:
                return web.json_response({
                    "success": False,
                    "error": "Authentication token is required"
                }, status=401)
            
            # Validate token to get user ID
            auth_result = await order_manager.auth_client.validate_token(token)
            
            if not auth_result.get('valid'):
                return web.json_response({
                    "success": False,
                    "error": "Invalid authentication token"
                }, status=401)
            
            user_id = auth_result.get('userId')
            
            # Get pagination parameters
            limit = int(request.query.get('limit', '50'))
            offset = int(request.query.get('offset', '0'))
            
            # Limit maximum results
            if limit > 100:
                limit = 100
            
            # Get user orders
            result = await order_manager.get_user_orders(user_id, limit, offset)
            
            return web.json_response(result)
            
        except ValueError:
            return web.json_response({
                "success": False,
                "error": "Invalid pagination parameters"
            }, status=400)
        except Exception as e:
            logger.error(f"Error handling user orders query: {e}")
            return web.json_response({
                "success": False,
                "error": "Server error processing orders query"
            }, status=500)
    
    return get_user_orders_handler

async def handle_health_check(request):
    """Simple health check endpoint"""
    return web.json_response({
        'status': 'UP',
        'timestamp': int(time.time())
    })

def handle_readiness_check(order_manager):
    """Readiness check endpoint that verifies database connection"""
    async def readiness_handler(request):
        try:
            # Check database connection
            db_ready = await order_manager.order_store.check_connection()
            
            # Check Redis connection
            redis_ready = await order_manager.redis.ping()
            
            if db_ready and redis_ready:
                return web.json_response({
                    'status': 'READY',
                    'timestamp': int(time.time()),
                    'checks': {
                        'database': 'UP',
                        'redis': 'UP'
                    }
                })
            else:
                return web.json_response({
                    'status': 'NOT READY',
                    'reason': 'One or more dependencies are not available',
                    'checks': {
                        'database': 'UP' if db_ready else 'DOWN',
                        'redis': 'UP' if redis_ready else 'DOWN'
                    }
                }, status=503)
        except Exception as e:
            logger.error(f"Readiness check failed: {e}")
            return web.json_response({
                'status': 'NOT READY',
                'reason': str(e)
            }, status=503)
    
    return readiness_handler