# source/api/rest_routes.py
import logging
import json
import aiohttp_cors
import os
import time
from aiohttp import web

logger = logging.getLogger('rest_api')


def setup_rest_app(auth_manager):
    """Set up the REST API application with routes and middleware"""
    app = web.Application()

    # Add routes
    app.router.add_post('/api/auth/login', handle_login(auth_manager))
    app.router.add_post('/api/auth/logout', handle_logout(auth_manager))
    app.router.add_post('/api/auth/refresh', handle_refresh_token(auth_manager))
    app.router.add_post('/api/auth/validate', handle_validate_token(auth_manager))
    app.router.add_get('/health', handle_health_check)
    app.router.add_get('/readiness', handle_readiness_check(auth_manager))

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


def handle_login(auth_manager):
    """Login route handler"""

    async def login_handler(request):
        try:
            # Parse request body
            data = await request.json()
            username = data.get('username')
            password = data.get('password')

            if not username or not password:
                return web.json_response({
                    'success': False,
                    'error': 'Username and password are required'
                }, status=400)

            # Call auth manager
            result = await auth_manager.login(username, password)

            if not result['success']:
                return web.json_response({
                    'success': False,
                    'error': result.get('error', 'Authentication failed')
                }, status=401)

            # Set secure cookie with access token (optional)
            response = web.json_response(result)

            # Only set cookie in production environments with HTTPS
            if os.getenv('ENVIRONMENT', 'development') == 'production':
                response.set_cookie(
                    'auth_token',
                    result['accessToken'],
                    httponly=True,
                    secure=True,
                    samesite='Strict',
                    max_age=result['expiresIn']
                )

            return response
        except json.JSONDecodeError:
            return web.json_response({
                'success': False,
                'error': 'Invalid JSON in request'
            }, status=400)
        except Exception as e:
            logger.error(f"Login handler error: {e}")
            return web.json_response({
                'success': False,
                'error': 'Authentication service error'
            }, status=500)

    return login_handler


def handle_logout(auth_manager):
    """Logout route handler"""

    async def logout_handler(request):
        try:
            # Get token from Authorization header or request body
            auth_header = request.headers.get('Authorization')
            data = await request.json() if request.has_body else {}

            access_token = None
            refresh_token = data.get('refreshToken')
            logout_all = data.get('logoutAll', False)

            if auth_header and auth_header.startswith('Bearer '):
                access_token = auth_header[7:]
            else:
                access_token = data.get('accessToken')

            if not access_token:
                return web.json_response({
                    'success': False,
                    'error': 'Access token is required'
                }, status=400)

            # Call auth manager
            result = await auth_manager.logout(access_token, refresh_token, logout_all)

            # Clear auth cookie if it exists
            response = web.json_response(result)
            response.del_cookie('auth_token')

            return response
        except Exception as e:
            logger.error(f"Logout handler error: {e}")
            return web.json_response({
                'success': False,
                'error': 'Logout failed'
            }, status=500)

    return logout_handler


def handle_refresh_token(auth_manager):
    """Refresh token route handler"""

    async def refresh_token_handler(request):
        try:
            # Parse request body
            data = await request.json()
            refresh_token = data.get('refreshToken')

            if not refresh_token:
                return web.json_response({
                    'success': False,
                    'error': 'Refresh token is required'
                }, status=400)

            # Call auth manager
            result = await auth_manager.refresh_token(refresh_token)

            if not result['success']:
                return web.json_response({
                    'success': False,
                    'error': result.get('error', 'Token refresh failed')
                }, status=401)

            # Set secure cookie with new access token (optional)
            response = web.json_response(result)

            # Only set cookie in production environments with HTTPS
            if os.getenv('ENVIRONMENT', 'development') == 'production':
                response.set_cookie(
                    'auth_token',
                    result['accessToken'],
                    httponly=True,
                    secure=True,
                    samesite='Strict',
                    max_age=result['expiresIn']
                )

            return response
        except json.JSONDecodeError:
            return web.json_response({
                'success': False,
                'error': 'Invalid JSON in request'
            }, status=400)
        except Exception as e:
            logger.error(f"Refresh token handler error: {e}")
            return web.json_response({
                'success': False,
                'error': 'Token refresh failed'
            }, status=500)

    return refresh_token_handler


def handle_validate_token(auth_manager):
    """Validate token route handler"""

    async def validate_token_handler(request):
        try:
            # Get token from Authorization header or request body
            auth_header = request.headers.get('Authorization')
            data = await request.json() if request.has_body else {}

            token = None
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header[7:]
            else:
                token = data.get('token')

            if not token:
                return web.json_response({
                    'valid': False,
                    'error': 'Token is required'
                }, status=400)

            # Call auth manager
            result = await auth_manager.validate_token(token)

            return web.json_response(result)
        except Exception as e:
            logger.error(f"Validate token handler error: {e}")
            return web.json_response({
                'valid': False,
                'error': 'Token validation failed'
            }, status=500)

    return validate_token_handler


async def handle_health_check(request):
    """Simple health check endpoint"""
    return web.json_response({
        'status': 'UP',
        'timestamp': int(time.time())
    })


def handle_readiness_check(auth_manager):
    """Readiness check endpoint that verifies database connection"""

    async def readiness_handler(request):
        try:
            # Check database connection
            connection_alive = await auth_manager.db.check_connection()

            if connection_alive:
                return web.json_response({
                    'status': 'READY',
                    'timestamp': int(time.time())
                })
            else:
                return web.json_response({
                    'status': 'NOT READY',
                    'reason': 'Database connection failed'
                }, status=503)
        except Exception as e:
            logger.error(f"Readiness check failed: {e}")
            return web.json_response({
                'status': 'NOT READY',
                'reason': str(e)
            }, status=503)

    return readiness_handler
