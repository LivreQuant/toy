# source/api/handlers/profile_handlers.py
import logging
import json
from aiohttp import web
from opentelemetry import trace

from source.utils.tracing import optional_trace_span
from source.utils.security import sanitize_input

logger = logging.getLogger('profile_handlers')


def handle_update_profile(auth_manager):
    """Profile update route handler"""
    tracer = trace.get_tracer("rest_api")

    async def update_profile_handler(request):
        with optional_trace_span(tracer, "handle_update_profile") as span:
            span.set_attribute("http.method", "PUT")
            span.set_attribute("http.route", "/api/auth/profile")
            
            try:
                # Get user ID from token
                auth_header = request.headers.get('Authorization')
                span.set_attribute("auth_header_present", auth_header is not None)
                
                if not auth_header or not auth_header.startswith('Bearer '):
                    span.set_attribute("error", "Missing or invalid authorization header")
                    return web.json_response({
                        'success': False,
                        'error': 'Authentication required'
                    }, status=401)
                
                access_token = auth_header[7:]
                token_data = auth_manager.token_manager.validate_access_token(access_token)
                
                if not token_data.get('valid'):
                    span.set_attribute("error", "Invalid token")
                    return web.json_response({
                        'success': False,
                        'error': 'Invalid or expired token'
                    }, status=401)
                
                user_id = token_data.get('user_id')
                span.set_attribute("user_id", str(user_id))
                
                # Parse request body
                data = await request.json()
                
                # Sanitize inputs
                profile_data = {
                    'username': sanitize_input(data.get('username')),
                    'email': sanitize_input(data.get('email')),
                    'first_name': sanitize_input(data.get('firstName')),
                    'last_name': sanitize_input(data.get('lastName')),
                    'display_name': sanitize_input(data.get('displayName')),
                    'bio': sanitize_input(data.get('bio')),
                    'profile_picture_url': sanitize_input(data.get('profilePictureUrl')),
                    'preferences': data.get('preferences', {})
                }
                
                # Call auth manager
                result = await auth_manager.update_profile(user_id, profile_data)
                
                span.set_attribute("update.success", result.get('success', False))
                if not result.get('success', False):
                    span.set_attribute("update.error", result.get('error', 'Update failed'))
                
                status = 200 if result.get('success', False) else 400
                return web.json_response(result, status=status)
                
            except json.JSONDecodeError:
                logger.error("Invalid JSON in profile update request")
                span.set_attribute("error", "Invalid JSON in request")
                return web.json_response({
                    'success': False,
                    'error': 'Invalid JSON in request'
                }, status=400)
            except Exception as e:
                logger.error(f"Profile update handler error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return web.json_response({
                    'success': False,
                    'error': 'Profile update service error'
                }, status=500)

    return update_profile_handler
