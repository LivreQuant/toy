# source/api/handlers/signup_handlers.py
import logging
import json
from aiohttp import web
from opentelemetry import trace

from source.utils.tracing import optional_trace_span
from source.utils.security import is_strong_password, sanitize_input

logger = logging.getLogger('signup_handlers')

def handle_signup(auth_manager):
    """Signup route handler"""
    tracer = trace.get_tracer("rest_api")

    async def signup_handler(request):
        with optional_trace_span(tracer, "handle_signup") as span:
            span.set_attribute("http.method", "POST")
            span.set_attribute("http.route", "/api/auth/signup")
            
            try:
                # Parse request body
                data = await request.json()
                username = sanitize_input(data.get('username'))
                email = sanitize_input(data.get('email'))
                password = data.get('password')  # Don't sanitize passwords
                
                logger.debug(f"Processing signup for username: {username}, email: {email}")
                span.set_attribute("username", username)
                span.set_attribute("email", email)
                
                # Validate inputs
                if not username or not email or not password:
                    logger.debug("Missing required fields")
                    span.set_attribute("error", "Missing required fields")
                    return web.json_response({
                        'success': False,
                        'error': 'Username, email, and password are required'
                    }, status=400)
                
                # Validate password strength
                if not is_strong_password(password):
                    logger.debug("Password doesn't meet strength requirements")
                    span.set_attribute("error", "Weak password")
                    return web.json_response({
                        'success': False,
                        'error': 'Password must be at least 8 characters long and include uppercase, lowercase, number, and special character'
                    }, status=400)
                
                # Call auth manager
                result = await auth_manager.signup(username, email, password)
                logger.debug(f"Signup result: {result}")
                
                span.set_attribute("signup.success", result.get('success', False))
                if not result.get('success', False):
                    logger.debug(f"Signup failed: {result.get('error', 'Unknown error')}")
                    span.set_attribute("signup.error", result.get('error', 'Unknown error'))
                
                # Return appropriate status code
                status = 201 if result.get('success', False) else 400
                return web.json_response(result, status=status)
                
            except json.JSONDecodeError:
                logger.error("Invalid JSON in signup request")
                span.set_attribute("error", "Invalid JSON in request")
                return web.json_response({
                    'success': False,
                    'error': 'Invalid JSON in request'
                }, status=400)
            except Exception as e:
                logger.error(f"Signup handler error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return web.json_response({
                    'success': False,
                    'error': 'Registration service error'
                }, status=500)

    return signup_handler

def handle_verify_email(auth_manager):
    """Email verification route handler"""
    tracer = trace.get_tracer("rest_api")

    async def verify_email_handler(request):
        with optional_trace_span(tracer, "handle_verify_email") as span:
            span.set_attribute("http.method", "POST")
            span.set_attribute("http.route", "/api/auth/verify-email")
            
            try:
                # Parse request body
                data = await request.json()
                user_id = data.get('userId')
                verification_code = sanitize_input(data.get('code'))
                
                logger.debug(f"Processing email verification for user: {user_id}")
                span.set_attribute("user_id", str(user_id))
                
                if not user_id or not verification_code:
                    logger.debug("Missing required fields")
                    span.set_attribute("error", "Missing required fields")
                    return web.json_response({
                        'success': False,
                        'error': 'User ID and verification code are required'
                    }, status=400)
                
                # Call auth manager
                result = await auth_manager.verify_email(user_id, verification_code)
                
                span.set_attribute("verification.success", result.get('success', False))
                if not result.get('success', False):
                    span.set_attribute("verification.error", result.get('error', 'Verification failed'))
                
                status = 200 if result.get('success', False) else 400
                return web.json_response(result, status=status)
                
            except json.JSONDecodeError:
                logger.error("Invalid JSON in verification request")
                span.set_attribute("error", "Invalid JSON in request")
                return web.json_response({
                    'success': False,
                    'error': 'Invalid JSON in request'
                }, status=400)
            except Exception as e:
                logger.error(f"Verification handler error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return web.json_response({
                    'success': False,
                    'error': 'Verification service error'
                }, status=500)

    return verify_email_handler

def handle_resend_verification(auth_manager):
    """Resend verification code handler"""
    tracer = trace.get_tracer("rest_api")

    async def resend_verification_handler(request):
        with optional_trace_span(tracer, "handle_resend_verification") as span:
            span.set_attribute("http.method", "POST")
            span.set_attribute("http.route", "/api/auth/resend-verification")
            
            try:
                # Parse request body
                data = await request.json()
                user_id = data.get('userId')
                
                logger.debug(f"Processing verification resend for user: {user_id}")
                span.set_attribute("user_id", str(user_id))
                
                if not user_id:
                    logger.debug("Missing user ID")
                    span.set_attribute("error", "Missing user ID")
                    return web.json_response({
                        'success': False,
                        'error': 'User ID is required'
                    }, status=400)
                
                # Call auth manager
                result = await auth_manager.resend_verification(user_id)
                
                span.set_attribute("resend.success", result.get('success', False))
                if not result.get('success', False):
                    span.set_attribute("resend.error", result.get('error', 'Resend failed'))
                
                status = 200 if result.get('success', False) else 400
                return web.json_response(result, status=status)
                
            except json.JSONDecodeError:
                logger.error("Invalid JSON in resend verification request")
                span.set_attribute("error", "Invalid JSON in request")
                return web.json_response({
                    'success': False,
                    'error': 'Invalid JSON in request'
                }, status=400)
            except Exception as e:
                logger.error(f"Resend verification handler error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return web.json_response({
                    'success': False,
                    'error': 'Verification service error'
                }, status=500)

    return resend_verification_handler