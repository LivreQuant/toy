# source/api/rest/simulator_handlers.py
"""
REST API request handlers for simulator operations.
Simplified for singleton session model.
"""
import logging
from aiohttp import web
from opentelemetry import trace

from source.utils.metrics import track_simulator_operation
from source.api.rest.utils import create_error_response
from source.api.rest.decorators import with_auth_validation

logger = logging.getLogger('simulator_handlers')
_tracer = trace.get_tracer("simulator_handlers")


@with_auth_validation(operation_type="start", metrics_category="simulator")
async def handle_start_simulator(request, user_id):
    """
    Handle simulator start request.
    """
    session_manager = request.app['session_manager']

    # Start simulator (using user ID from validated token)
    simulator_id, endpoint, error = await session_manager.start_simulator(user_id)

    # Set span attributes for tracing
    span = trace.get_current_span()
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
        'status': 'STARTING',
    })


@with_auth_validation(operation_type="stop", metrics_category="simulator")
async def handle_stop_simulator(request, user_id):
    """
    Handle simulator stop request.
    """
    session_manager = request.app['session_manager']

    # Stop simulator associated with session
    success, error = await session_manager.stop_simulator()

    # Set span attributes for tracing
    span = trace.get_current_span()
    span.set_attribute("stop_success", success)

    if not success:
        span.set_attribute("error", error)
        track_simulator_operation("stop", "error_validation")
        return create_error_response(error, 400)

    track_simulator_operation("stop", "success")
    return web.json_response({'success': True})