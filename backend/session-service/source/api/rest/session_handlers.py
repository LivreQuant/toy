# source/api/rest/session_handlers.py
"""
REST API request handlers for session operations.
Simplified for singleton session model.
"""
import logging
from aiohttp import web
from opentelemetry import trace

from source.utils.metrics import track_session_operation
from source.utils.tracing import optional_trace_span
from source.api.rest.utils import validate_auth_token, create_error_response

logger = logging.getLogger('session_handlers')
_tracer = trace.get_tracer("session_handlers")


async def handle_session_info(request):
    """
    Handle session information request.
    In singleton mode, returns info about the pre-initialized session.

    Args:
        request: HTTP request

    Returns:
        JSON response
    """
    with optional_trace_span(_tracer, "handle_session_info") as span:
        session_manager = request.app['session_manager']
        singleton_session_id = request.app.get('singleton_session_id')
        
        # Optional validation of auth token
        user_id, validation, error_response = await validate_auth_token(request, span)
        if error_response:
            track_session_operation("info", "error_auth")
            return error_response
            
        span.set_attribute("session_id", singleton_session_id)
        span.set_attribute("user_id", user_id)

        # Get session info
        session = await session_manager.get_session(singleton_session_id)
        if not session:
            span.set_attribute("error", "Session not found")
            track_session_operation("info", "error_not_found")
            return create_error_response('Session not found', 404)

        # Get session metadata
        metadata = await session_manager.get_session_metadata(singleton_session_id)
        
        # Build response
        response = {
            'success': True,
            'sessionId': singleton_session_id,
            'userId': user_id,
            'status': session.status.value,
            'deviceId': metadata.get('device_id', 'unknown'),
            'created_at': session.created_at,
            'simulatorStatus': metadata.get('simulator_status', 'NONE'),
            'simulatorId': metadata.get('simulator_id')
        }

        track_session_operation("info", "success")
        return web.json_response(response)


async def handle_stop_session(request):
    """
    Handle session termination request.
    In singleton mode, we don't actually end the session, just clean up resources
    and reset the service to ready state.

    Args:
        request: HTTP request

    Returns:
        JSON response
    """
    with optional_trace_span(_tracer, "handle_stop_session") as span:
        session_manager = request.app['session_manager']
        state_manager = request.app['state_manager']
        singleton_session_id = request.app.get('singleton_session_id')

        # Optional validation of auth token
        user_id, validation, error_response = await validate_auth_token(request, span)
        if error_response:
            track_session_operation("end", "error_auth")
            return error_response

        span.set_attribute("session_id", singleton_session_id)
        span.set_attribute("user_id", user_id)

        # Check if there's a simulator running
        metadata = await session_manager.get_session_metadata(singleton_session_id)
        simulator_running = False
        simulator_id = None

        if metadata:
            simulator_id = metadata.get('simulator_id')
            simulator_status = metadata.get('simulator_status')

            # Check if simulator is in an active state
            active_states = ['CREATING', 'STARTING', 'RUNNING']
            if simulator_id and simulator_status and simulator_status in active_states:
                simulator_running = True
                span.set_attribute("simulator_running", True)
                span.set_attribute("simulator_id", simulator_id)
                span.set_attribute("simulator_status", simulator_status)

        # Stop simulator if running
        if simulator_running:
            logger.info(f"Stopping simulator {simulator_id} for session {singleton_session_id}")
            success, error = await session_manager.stop_simulator(singleton_session_id)

            if not success:
                logger.warning(f"Failed to stop simulator: {error}")
                span.set_attribute("simulator_stop_error", error)

        # Update session state but don't actually end it in singleton mode
        await session_manager.update_session_metadata(singleton_session_id, {
            'simulator_id': None,
            'simulator_status': 'NONE',
            'simulator_endpoint': None
        })

        # Reset the service to ready state
        await state_manager.reset_to_ready()
        logger.info("Reset service to ready state after session stop")

        track_session_operation("cleanup", "success")
        return web.json_response({
            'success': True,
            'message': 'Session resources cleaned up',
            'simulatorStopped': simulator_running
        })
