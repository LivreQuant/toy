# source/api/rest/simulator_handlers.py
"""
REST API request handlers for simulator operations.
Simplified for singleton session model.
"""
import logging
from aiohttp import web
from opentelemetry import trace

from source.utils.metrics import track_simulator_operation
from source.utils.tracing import optional_trace_span
from source.api.rest.utils import validate_auth_token, create_error_response

logger = logging.getLogger('simulator_handlers')
_tracer = trace.get_tracer("simulator_handlers")


async def handle_start_simulator(request):
    """
    Handle simulator start request.

    Args:
        request: HTTP request

    Returns:
        JSON response
    """
    with optional_trace_span(_tracer, "handle_start_simulator") as span:
        session_manager = request.app['session_manager']
        singleton_session_id = request.app.get('singleton_session_id')
        singleton_user_id = request.app.get('singleton_user_id')
        
        # Optional validation of auth token
        user_id, validation, error_response = await validate_auth_token(request, span)
        if error_response:
            track_simulator_operation("start", "error_auth")
            return error_response
            
        span.set_attribute("session_id", singleton_session_id)
        span.set_attribute("user_id", user_id)

        # Start simulator (using singleton session)
        simulator_id, endpoint, error = await session_manager.start_simulator(
            singleton_session_id, 
            singleton_user_id
        )
        
        span.set_attribute("simulator_id", simulator_id or "none")
        span.set_attribute("endpoint", endpoint or "none")

        if error:
            span.set_attribute("error", error)
            track_simulator_operation("start", "error_validation")
            return create_error_response(error, 400)

        track_simulator_operation("start", "success")
        return web.json_response({
            'success': True,
            'simulatorId': simulator_id,
            'status': 'STARTING',  # Indicate async start
        })


async def handle_stop_simulator(request):
    """
    Handle simulator stop request.

    Args:
        request: HTTP request

    Returns:
        JSON response
    """
    with optional_trace_span(_tracer, "handle_stop_simulator") as span:
        session_manager = request.app['session_manager']
        singleton_session_id = request.app.get('singleton_session_id')
        
        # Optional validation of auth token
        user_id, validation, error_response = await validate_auth_token(request, span)
        if error_response:
            track_simulator_operation("stop", "error_auth")
            return error_response
            
        span.set_attribute("session_id", singleton_session_id)
        span.set_attribute("user_id", user_id)

        # Stop simulator associated with session
        success, error = await session_manager.stop_simulator(singleton_session_id)
        span.set_attribute("stop_success", success)

        if not success:
            span.set_attribute("error", error)
            track_simulator_operation("stop", "error_validation")
            return create_error_response(error, 400)

        track_simulator_operation("stop", "success")
        return web.json_response({'success': True})
    