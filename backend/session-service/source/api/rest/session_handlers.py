# source/api/rest/session_handlers.py
"""
REST API request handlers for session operations.
"""
import logging
import json
from aiohttp import web
from opentelemetry import trace

from source.utils.metrics import track_session_operation
from source.utils.tracing import optional_trace_span
from source.api.rest.utils import validate_auth_token, create_error_response

logger = logging.getLogger('session_handlers')
_tracer = trace.get_tracer("session_handlers")


async def handle_start_session(request):
    """
    Handle session creation request with deviceId in request body
    and user info from Authorization header.

    Args:
        request: HTTP request

    Returns:
        JSON response
    """
    with optional_trace_span(_tracer, "handle_start_session") as span:
        session_manager = request.app['session_manager']

        try:
            # Parse request body
            try:
                data = await request.json()
                logger.debug(f"Parsed session creation request data: {data}")
            except json.JSONDecodeError:
                span.set_attribute("error", "Invalid JSON in request body")
                track_session_operation("create", "error_json")
                return create_error_response('Invalid JSON in request body', 400)

            # Extract deviceId from request
            device_id = data.get('deviceId')
            span.set_attribute("device_id", device_id)

            if not device_id:
                span.set_attribute("error", "Missing deviceId")
                track_session_operation("create", "error_missing_device")
                return create_error_response('Missing deviceId', 400)

            # Validate the token and get user ID
            user_id, validation, error_response = await validate_auth_token(request, span)
            if error_response:
                track_session_operation("create", "error_auth")
                return error_response

            # Get client IP
            client_ip = request.remote
            span.set_attribute("client_ip", client_ip)

            # Create session with device_id
            session_id, is_new = await session_manager.create_session(user_id, device_id, validation.get('token'),
                                                                      client_ip)

            if not session_id:
                span.set_attribute("error", "Session creation failed")
                track_session_operation("create", "error_internal")
                return create_error_response('Failed to create session', 500)

            span.set_attribute("session_id", session_id)
            span.set_attribute("is_new", is_new)
            track_session_operation("create", "success")

            return web.json_response({
                'success': True,
                'sessionId': session_id,
                'isNew': is_new
            })

        except Exception as e:
            logger.exception(f"Error creating session: {e}")
            span.record_exception(e)
            track_session_operation("create", "error_exception")
            return create_error_response('Server error during session creation', 500)


async def handle_stop_session(request):
    """
    Handle session termination request.
    Only requires a valid token - we'll look up the user's active session.
    If the session has a running simulator, it will be stopped first.

    Args:
        request: HTTP request

    Returns:
        JSON response
    """
    with optional_trace_span(_tracer, "handle_stop_session") as span:
        session_manager = request.app['session_manager']

        try:
            # Validate token and get user ID
            user_id, validation, error_response = await validate_auth_token(request, span)
            if error_response:
                track_session_operation("end", "error_auth")
                return error_response

            # Get the user's active session
            session, error_response = await session_manager.get_active_session(request, user_id, validation.get('token'), span)
            if error_response:
                track_session_operation("end", "error_no_session")
                return error_response

            session_id = session.session_id
            span.set_attribute("session_id", session_id)
            token = validation.get('token')

            # Check if there's a simulator running for this session
            # We can check session.metadata for simulator information
            simulator_running = False
            simulator_id = None

            if hasattr(session, 'metadata') and session.metadata:
                simulator_id = getattr(session.metadata, 'simulator_id', None)
                simulator_status = getattr(session.metadata, 'simulator_status', None)

                # Check if simulator is in an active state
                active_states = ['CREATING', 'STARTING', 'RUNNING']
                if simulator_id and simulator_status and simulator_status in active_states:
                    simulator_running = True
                    span.set_attribute("simulator_running", True)
                    span.set_attribute("simulator_id", simulator_id)
                    span.set_attribute("simulator_status", simulator_status)

            # Stop simulator first if needed
            if simulator_running:
                logger.info(f"Stopping simulator {simulator_id} before ending session {session_id}")
                sim_success, sim_error = await session_manager.stop_simulator(session_id, token)

                if not sim_success:
                    # Log the error but proceed with session termination
                    logger.warning(f"Failed to stop simulator during session termination: {sim_error}")
                    span.set_attribute("simulator_stop_error", sim_error)
                else:
                    logger.info(f"Successfully stopped simulator before ending session")

            # Now end the session
            success, error = await session_manager.end_session(session_id, token)
            span.set_attribute("end_success", success)

            if not success:
                span.set_attribute("error", error)
                # Determine status code based on error
                status = 400  # Default
                if "Invalid session or token" in error or "ownership" in error:
                    status = 401
                elif "not found" in error:
                    status = 404

                track_session_operation("end", "error_validation")
                return create_error_response(error, status)

            track_session_operation("end", "success")
            return web.json_response({
                'success': True,
                'simulatorStopped': simulator_running
            })

        except Exception as e:
            logger.exception(f"Error ending session: {e}")
            span.record_exception(e)
            track_session_operation("end", "error_exception")
            return create_error_response('Server error during session termination', 500)
