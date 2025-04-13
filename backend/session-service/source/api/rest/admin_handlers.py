# Add the handler to a new file source/api/rest/admin_handlers.py:
"""
Admin API handlers for service management.
"""
import logging
from aiohttp import web
from opentelemetry import trace

from source.utils.metrics import track_admin_operation
from source.utils.tracing import optional_trace_span

logger = logging.getLogger('admin_handlers')
_tracer = trace.get_tracer("admin_handlers")


async def handle_reset_service(request):
    """
    Handle manual service reset request.
    Used for administrative purposes to force reset a service to ready state.
    
    Args:
        request: HTTP request
        
    Returns:
        JSON response
    """
    with optional_trace_span(_tracer, "handle_reset_service") as span:
        # Get state manager
        state_manager = request.app['state_manager']

        # Get session manager
        session_manager = request.app['session_manager']

        # Check current state
        current_state = "READY" if state_manager.is_ready() else "ACTIVE"
        span.set_attribute("current_state", current_state)

        # If active, perform cleanup
        session_id = state_manager.get_active_session_id()
        if session_id:
            span.set_attribute("session_id", session_id)

            # Clean up session
            await session_manager.cleanup_session(session_id)
            logger.info(f"Cleaned up session {session_id} during forced reset")

        # Reset state
        result = await state_manager.reset_to_ready()
        span.set_attribute("reset_success", result)

        if result:
            logger.info("Service reset to READY state via admin request")
            return web.json_response({
                'success': True,
                'previousState': current_state,
                'currentState': 'READY'
            })
        else:
            logger.error("Failed to reset service state")
            return web.json_response({
                'success': False,
                'error': 'Failed to reset service state',
                'previousState': current_state
            }, status=500)
