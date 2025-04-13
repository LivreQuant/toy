# source/api/rest/session_handlers.py
"""
REST API request handlers for session operations.
Simplified for singleton session model.
"""
import logging
from aiohttp import web
from opentelemetry import trace

from source.utils.metrics import track_session_operation
from source.api.rest.utils import create_error_response
from source.api.rest.decorators import with_auth_validation

logger = logging.getLogger('session_handlers')
_tracer = trace.get_tracer("session_handlers")


@with_auth_validation(operation_type="info", metrics_category="session")
async def handle_session_info(request, user_id):
    """
    Handle session information request.
    In singleton mode, returns info about the pre-initialized session.
    """
    session_manager = request.app['session_manager']
    session_id = session_manager.session_id

    # Get session info
    session = await session_manager.get_session()
    if not session:
        track_session_operation("info", "error_not_found")
        return create_error_response('Session not found', 404)

    # Get session metadata
    metadata = await session_manager.get_session_metadata()

    # Build response
    response = {
        'success': True,
        'sessionId': session_id,
        'userId': user_id,
        'status': session.status.value,
        'deviceId': metadata.get('device_id', 'unknown'),
        'created_at': session.created_at,
        'simulatorStatus': metadata.get('simulator_status', 'NONE'),
        'simulatorId': metadata.get('simulator_id')
    }

    track_session_operation("info", "success")
    return web.json_response(response)


@with_auth_validation(operation_type="stop", metrics_category="session")
async def handle_stop_session(request):
    """
    Handle session termination request.
    In singleton mode, we don't actually end the session, just clean up resources
    and reset the service to ready state.
    """
    session_manager = request.app['session_manager']
    state_manager = request.app['state_manager']
    session_id = session_manager.session_id

    # Check if there's a simulator running
    metadata = await session_manager.get_session_metadata()
    simulator_running = False
    simulator_id = None

    if metadata:
        simulator_id = metadata.get('simulator_id')
        simulator_status = metadata.get('simulator_status')

        # Check if simulator is in an active state
        active_states = ['CREATING', 'STARTING', 'RUNNING']
        if simulator_id and simulator_status and simulator_status in active_states:
            simulator_running = True

    # Stop simulator if running
    if simulator_running:
        logger.info(f"Stopping simulator {simulator_id} for session {session_id}")
        success, error = await session_manager.stop_simulator()

        if not success:
            logger.warning(f"Failed to stop simulator: {error}")

    # Update session state but don't actually end it in singleton mode
    await session_manager.update_session_metadata({
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