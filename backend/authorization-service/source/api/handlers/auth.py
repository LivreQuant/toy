# source/api/handlers/auth_handlers.py
import logging
import json
import os
from aiohttp import web
from opentelemetry import trace

from source.utils.tracing import optional_trace_span

logger = logging.getLogger('auth_handlers')


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
