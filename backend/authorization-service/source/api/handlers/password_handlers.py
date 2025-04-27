# source/api/handlers/password_handlers.py
import logging
import json
from aiohttp import web
from opentelemetry import trace

from source.utils.tracing import optional_trace_span
from source.utils.security import is_strong_password, sanitize_input

logger = logging.getLogger('password_handlers')

def handle_forgot_username(auth_manager):
    """Forgot username route handler"""
    tracer = trace.get_tracer("rest_api")

    async def forgot_username_handler(request):
        with optional_trace_span(tracer, "handle_forgot_username") as span:
            span.set_attribute("http.method", "POST")
            span.set_attribute("http.route", "/api/auth/forgot-username")
            
            try:
                # Parse request body
                data = await request.json()
                email = sanitize_input(data.get('email'))
                
                logger.debug(f"Processing forgot username for email: {email}")
                span.set_attribute("email", email)
                
                if not email:
                    logger.debug("Missing email")
                    span.set_attribute("error", "Missing email")
                    return web.json_response({
                        'success': False,
                        'error': 'Email is required'
                    }, status=400)
                
                # Call auth manager
                result = await auth_manager.forgot_username(email)
                
                # Always return success to prevent email enumeration
                return web.json_response({
                    'success': True,
                    'message': 'If your email is registered, you will receive your username shortly.'
                })
                
            except json.JSONDecodeError:
                logger.error("Invalid JSON in forgot username request")
                span.set_attribute("error", "Invalid JSON in request")
                return web.json_response({
                    'success': False,
                    'error': 'Invalid JSON in request'
                }, status=400)
            except Exception as e:
                logger.error(f"Forgot username handler error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return web.json_response({
                    'success': False,
                    'error': 'Service error'
                }, status=500)

    return forgot_username_handler

def handle_forgot_password(auth_manager):
    """Forgot password route handler"""
    tracer = trace.get_tracer("rest_api")

    async def forgot_password_handler(request):
        with optional_trace_span(tracer, "handle_forgot_password") as span:
            span.set_attribute("http.method", "POST")
            span.set_attribute("http.route", "/api/auth/forgot-password")
            
            try:
                # Parse request body
                data = await request.json()
                email = sanitize_input(data.get('email'))
                
                logger.debug(f"Processing forgot password for email: {email}")
                span.set_attribute("email", email)
                
                if not email:
                    logger.debug("Missing email")
                    span.set_attribute("error", "Missing email")
                    return web.json_response({
                        'success': False,
                        'error': 'Email is required'
                    }, status=400)
                
                # Call auth manager
                result = await auth_manager.forgot_password(email)
                
                # Always return success to prevent email enumeration
                return web.json_response({
                    'success': True,
                    'message': 'If your email is registered, you will receive a password reset link shortly.'
                })
                
            except json.JSONDecodeError:
                logger.error("Invalid JSON in forgot password request")
                span.set_attribute("error", "Invalid JSON in request")
                return web.json_response({
                    'success': False,
                    'error': 'Invalid JSON in request'
                }, status=400)
            except Exception as e:
                logger.error(f"Forgot password handler error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return web.json_response({
                    'success': False,
                    'error': 'Service error'
                }, status=500)

    return forgot_password_handler

def handle_reset_password(auth_manager):
    """Reset password route handler"""
    tracer = trace.get_tracer("rest_api")

    async def reset_password_handler(request):
        with optional_trace_span(tracer, "handle_reset_password") as span:
            span.set_attribute("http.method", "POST")
            span.set_attribute("http.route", "/api/auth/reset-password")
            
            try:
                # Parse request body
                data = await request.json()
                token = data.get('token')
                new_password = data.get('newPassword')
                
                logger.debug("Processing password reset")
                span.set_attribute("token_provided", token is not None)
                
                if not token or not new_password:
                    logger.debug("Missing required fields")
                    span.set_attribute("error", "Missing required fields")
                    return web.json_response({
                        'success': False,
                        'error': 'Token and new password are required'
                    }, status=400)
                
                # Validate password strength
                if not is_strong_password(new_password):
                    logger.debug("Password doesn't meet strength requirements")
                    span.set_attribute("error", "Weak password")
                    return web.json_response({
                        'success': False,
                        'error': 'Password must be at least 8 characters long and include uppercase, lowercase, number, and special character'
                    }, status=400)
                
                # Call auth manager
                result = await auth_manager.reset_password(token, new_password)
                
                span.set_attribute("reset.success", result.get('success', False))
                if not result.get('success', False):
                    span.set_attribute("reset.error", result.get('error', 'Reset failed'))
                
                status = 200 if result.get('success', False) else 400
                return web.json_response(result, status=status)
                
            except json.JSONDecodeError:
                logger.error("Invalid JSON in reset password request")
                span.set_attribute("error", "Invalid JSON in request")
                return web.json_response({
                    'success': False,
                    'error': 'Invalid JSON in request'
                }, status=400)
            except Exception as e:
                logger.error(f"Reset password handler error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return web.json_response({
                    'success': False,
                    'error': 'Password reset service error'
                }, status=500)

    return reset_password_handler