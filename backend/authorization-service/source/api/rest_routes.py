# source/api/rest_routes.py
import logging
import json
import aiohttp_cors
import os
import time
from aiohttp import web
from opentelemetry import trace

from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from source.utils.tracing import optional_trace_span

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

    # Add this new route for metrics
    app.router.add_get('/metrics', handle_metrics)

    # Set up CORS
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Origin", "Accept"],
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        )
    })

    # Apply CORS to all routes
    for route in list(app.router.routes()):
        cors.add(route)

    return app

# Then add this new handler function:
async def handle_metrics(request):
    """Expose Prometheus metrics"""
    return web.Response(
        body=generate_latest(),
        content_type=CONTENT_TYPE_LATEST
    )

def handle_login(auth_manager):
    """Login route handler"""
    tracer = trace.get_tracer("rest_api")

    async def login_handler(request):
        with optional_trace_span(tracer, "handle_login") as span:
            span.set_attribute("http.method", "POST")
            span.set_attribute("http.route", "/api/auth/login")
            
            try:
                logger.debug("Processing login request")
                # Parse request body
                data = await request.json()
                username = data.get('username')
                password = data.get('password')
                
                logger.debug(f"Login request for username: {username}")
                span.set_attribute("username", username)
                
                if not username or not password:
                    logger.debug(f"Missing credentials: username={username is not None}, password={password is not None}")
                    span.set_attribute("error", "Missing username or password")
                    return web.json_response({
                        'success': False,
                        'error': 'Username and password are required'
                    }, status=400)

                # Call auth manager
                logger.debug("Calling auth_manager.login")
                result = await auth_manager.login(username, password)
                logger.debug(f"Login result: {result}")
                
                span.set_attribute("login.success", result.get('success', False))
                if not result.get('success', False):
                    logger.debug(f"Login failed: {result.get('error', 'Authentication failed')}")
                    span.set_attribute("login.error", result.get('error', 'Authentication failed'))

                if not result['success']:
                    return web.json_response({
                        'success': False,
                        'error': result.get('error', 'Authentication failed')
                    }, status=401)

                # Process successful login
                logger.debug("Login successful, preparing response")
                
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
                
                logger.debug("Login response prepared")
                return response
                
            except json.JSONDecodeError:
                logger.error("Invalid JSON in login request")
                span.set_attribute("error", "Invalid JSON in request")
                return web.json_response({
                    'success': False,
                    'error': 'Invalid JSON in request'
                }, status=400)
            except Exception as e:
                logger.error(f"Login handler error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return web.json_response({
                    'success': False,
                    'error': 'Authentication service error'
                }, status=500)

    return login_handler

def handle_logout(auth_manager):
    """Logout route handler"""
    tracer = trace.get_tracer("rest_api")

    async def logout_handler(request):
        with optional_trace_span(tracer, "handle_logout") as span:
            span.set_attribute("http.method", "POST")
            span.set_attribute("http.route", "/api/auth/logout")
            
            try:
                # Get token from Authorization header or request body
                auth_header = request.headers.get('Authorization')
                span.set_attribute("auth_header_present", auth_header is not None)
                
                data = await request.json() if request.has_body else {}

                access_token = None
                refresh_token = data.get('refreshToken')
                logout_all = data.get('logoutAll', False)
                
                span.set_attribute("refresh_token_present", refresh_token is not None)
                span.set_attribute("logout_all", logout_all)

                if auth_header and auth_header.startswith('Bearer '):
                    access_token = auth_header[7:]
                else:
                    access_token = data.get('accessToken')

                if not access_token:
                    span.set_attribute("error", "Access token is required")
                    return web.json_response({
                        'success': False,
                        'error': 'Access token is required'
                    }, status=400)

                # Call auth manager
                result = await auth_manager.logout(access_token, refresh_token, logout_all)
                span.set_attribute("logout.success", result.get('success', False))
                
                # Clear auth cookie if it exists
                response = web.json_response(result)
                response.del_cookie('auth_token')

                return response
            except Exception as e:
                logger.error(f"Logout handler error: {e}")
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return web.json_response({
                    'success': False,
                    'error': 'Logout failed'
                }, status=500)

    return logout_handler


def handle_refresh_token(auth_manager):
    """Refresh token route handler"""
    tracer = trace.get_tracer("rest_api")

    async def refresh_token_handler(request):
        with optional_trace_span(tracer, "handle_refresh_token") as span:
            span.set_attribute("http.method", "POST")
            span.set_attribute("http.route", "/api/auth/refresh")
            
            try:
                # Parse request body
                data = await request.json()
                refresh_token = data.get('refreshToken')
                span.set_attribute("refresh_token_present", refresh_token is not None)

                if not refresh_token:
                    span.set_attribute("error", "Refresh token is required")
                    return web.json_response({
                        'success': False,
                        'error': 'Refresh token is required'
                    }, status=400)

                # Call auth manager
                result = await auth_manager.refresh_token(refresh_token)
                span.set_attribute("refresh.success", result.get('success', False))
                
                if not result.get('success', False):
                    span.set_attribute("refresh.error", result.get('error', 'Token refresh failed'))

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
                span.set_attribute("error", "Invalid JSON in request")
                return web.json_response({
                    'success': False,
                    'error': 'Invalid JSON in request'
                }, status=400)
            except Exception as e:
                logger.error(f"Refresh token handler error: {e}")
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return web.json_response({
                    'success': False,
                    'error': 'Token refresh failed'
                }, status=500)

    return refresh_token_handler


def handle_validate_token(auth_manager):
    """Validate token route handler"""
    tracer = trace.get_tracer("rest_api")

    async def validate_token_handler(request):
        with optional_trace_span(tracer, "handle_validate_token") as span:
            span.set_attribute("http.method", "POST")
            span.set_attribute("http.route", "/api/auth/validate")
            
            try:
                # Get token from Authorization header or request body
                auth_header = request.headers.get('Authorization')
                span.set_attribute("auth_header_present", auth_header is not None)
                
                data = await request.json() if request.has_body else {}

                token = None
                if auth_header and auth_header.startswith('Bearer '):
                    token = auth_header[7:]
                else:
                    token = data.get('token')

                if not token:
                    span.set_attribute("error", "Token is required")
                    return web.json_response({
                        'valid': False,
                        'error': 'Token is required'
                    }, status=400)

                # Call auth manager
                result = await auth_manager.validate_token(token)
                span.set_attribute("token.valid", result.get('valid', False))
                
                return web.json_response(result)
            except Exception as e:
                logger.error(f"Validate token handler error: {e}")
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return web.json_response({
                    'valid': False,
                    'error': 'Token validation failed'
                }, status=500)

    return validate_token_handler


async def handle_health_check(request):
    """Simple health check endpoint"""
    tracer = trace.get_tracer("rest_api")
    
    with optional_trace_span(tracer, "health_check") as span:
        span.set_attribute("http.method", "GET")
        span.set_attribute("http.route", "/health")
        
        # Check if monitoring services are properly configured
        monitoring_status = {
            "metrics": os.getenv('METRICS_PORT', '9090').isdigit(),  # Check if metrics port is configured
            "tracing": os.getenv('ENABLE_TRACING', 'true').lower() == 'true'
        }
        
        return web.json_response({
            'status': 'UP',
            'timestamp': int(time.time())
        })


def handle_readiness_check(auth_manager):
    """Readiness check endpoint that verifies database connection"""
    tracer = trace.get_tracer("rest_api")

    async def readiness_handler(request):
        with optional_trace_span(tracer, "readiness_check") as span:
            span.set_attribute("http.method", "GET")
            span.set_attribute("http.route", "/readiness")
            
            try:
                # Check database connection
                connection_alive = await auth_manager.db.check_connection()
                span.set_attribute("db.connection_alive", connection_alive)

                if connection_alive:
                    return web.json_response({
                        'status': 'READY',
                        'timestamp': int(time.time())
                    })
                else:
                    span.set_attribute("error", "Database connection failed")
                    return web.json_response({
                        'status': 'NOT READY',
                        'reason': 'Database connection failed'
                    }, status=503)
            except Exception as e:
                logger.error(f"Readiness check failed: {e}")
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return web.json_response({
                    'status': 'NOT READY',
                    'reason': str(e)
                }, status=503)

    return readiness_handler