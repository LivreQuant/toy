# source/api/handlers/feedback_handlers.py
import logging
import json
from aiohttp import web
from opentelemetry import trace

from source.utils.tracing import optional_trace_span
from source.utils.security import sanitize_input

logger = logging.getLogger('feedback_handlers')


def handle_feedback(auth_manager):
    """Feedback submission route handler"""
    tracer = trace.get_tracer("rest_api")

    async def feedback_handler(request):
        with optional_trace_span(tracer, "handle_feedback") as span:
            span.set_attribute("http.method", "POST")
            span.set_attribute("http.route", "/api/auth/feedback")
            
            try:
                # Try to get user ID from token if present (optional)
                user_id = None
                auth_header = request.headers.get('Authorization')
                
                if auth_header and auth_header.startswith('Bearer '):
                    access_token = auth_header[7:]
                    token_data = auth_manager.token_manager.validate_access_token(access_token)
                    
                    if token_data.get('valid'):
                        user_id = token_data.get('user_id')
                        span.set_attribute("user_id", str(user_id))
                
                # Parse request body
                data = await request.json()
                feedback_type = sanitize_input(data.get('type', 'general'))
                title = sanitize_input(data.get('title', ''))
                content = sanitize_input(data.get('content'))
                
                logger.debug(f"Processing feedback submission of type: {feedback_type}")
                span.set_attribute("feedback_type", feedback_type)
                
                if not content:
                    logger.debug("Missing feedback content")
                    span.set_attribute("error", "Missing feedback content")
                    return web.json_response({
                        'success': False,
                        'error': 'Feedback content is required'
                    }, status=400)
                
                # Call auth manager
                result = await auth_manager.submit_feedback(user_id, feedback_type, title, content)
                
                span.set_attribute("feedback.success", result.get('success', False))
                if not result.get('success', False):
                    span.set_attribute("feedback.error", result.get('error', 'Submission failed'))
                
                status = 201 if result.get('success', False) else 400
                return web.json_response(result, status=status)
                
            except json.JSONDecodeError:
                logger.error("Invalid JSON in feedback request")
                span.set_attribute("error", "Invalid JSON in request")
                return web.json_response({
                    'success': False,
                    'error': 'Invalid JSON in request'
                }, status=400)
            except Exception as e:
                logger.error(f"Feedback handler error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return web.json_response({
                    'success': False,
                    'error': 'Feedback service error'
                }, status=500)

    return feedback_handler
