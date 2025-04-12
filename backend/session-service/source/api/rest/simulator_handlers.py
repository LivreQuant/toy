# source/api/rest/simulator_handlers.py
"""
REST API request handlers for simulator operations.
"""
import logging
import json
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
    Requires token in Authorization header or query parameters.

    Args:
        request: HTTP request

    Returns:
        JSON response
    """
    with optional_trace_span(_tracer, "handle_start_simulator") as span:
        session_manager = request.app['session_manager']

        try:
            # Validate token and get user ID
            user_id, validation, error_response = await validate_auth_token(request, span)
            if error_response:
                track_simulator_operation("start", "error_auth")
                return error_response

            # Get active session for user
            session, error_response = await session_manager.get_active_session(request, user_id, validation.get('token'), span)
            if error_response:
                track_simulator_operation("start", "error_session")
                return error_response

            session_id = session.session_id
            logger.info(f"Using existing session {session_id} for user {user_id}")

            # Start simulator (session validation should happen inside start_simulator)
            simulator_id, endpoint, error = await session_manager.start_simulator(session_id, validation.get('token'))
            span.set_attribute("simulator_id", simulator_id or "none")
            span.set_attribute("endpoint", endpoint or "none")

            if error:
                span.set_attribute("error", error)
                # Determine status code based on error
                status = 400  # Default
                if "Invalid session or token" in error or "ownership" in error:
                    status = 401
                elif "not found" in error:
                    status = 404
                elif "already running" in error or "limit reached" in error:
                    status = 409  # Conflict
                track_simulator_operation("start", "error_validation")
                return create_error_response(error, status)

            track_simulator_operation("start", "success")
            return web.json_response({
                'success': True,
                'simulatorId': simulator_id,
                'status': 'STARTING',  # Indicate async start
            })

        except Exception as e:
            logger.exception(f"Error starting simulator: {e}")
            span.record_exception(e)
            track_simulator_operation("start", "error_exception")
            return create_error_response('Server error during simulator start', 500)


async def handle_stop_simulator(request):
    """
    Handle simulator stop request.
    Requires token in Authorization header, query parameters, or request body.

    Args:
        request: HTTP request

    Returns:
        JSON response
    """
    with optional_trace_span(_tracer, "handle_stop_simulator") as span:
        session_manager = request.app['session_manager']

        try:
            # For DELETE requests, we may have JSON or URL parameters
            has_body = request.content_type == 'application/json' and request.can_read_body

            # Validate token and get user ID
            user_id, validation, error_response = await validate_auth_token(request, span)
            if error_response:
                track_simulator_operation("stop", "error_auth")
                return error_response

            # Get active session for user
            session, error_response = await session_manager.get_active_session(request, user_id, validation.get('token'), span)
            if error_response:
                track_simulator_operation("stop", "error_session")
                return error_response

            session_id = session.session_id
            span.set_attribute("session_id", session_id)

            # Stop simulator associated with this session
            success, error = await session_manager.stop_simulator(session_id, validation.get('token'))
            span.set_attribute("stop_success", success)

            if not success:
                span.set_attribute("error", error)
                # Determine status code based on error
                status = 400  # Default
                if "Invalid session or token" in error or "ownership" in error:
                    status = 401
                elif "not found" in error or "no simulator" in error:
                    status = 404

                track_simulator_operation("stop", "error_validation")
                return create_error_response(error, status)

            track_simulator_operation("stop", "success")
            return web.json_response({'success': True})

        except json.JSONDecodeError:
            logger.warning("Invalid JSON received for stop simulator.")
            span.set_attribute("error", "Invalid JSON in request body")
            track_simulator_operation("stop", "error_json")
            return create_error_response('Invalid JSON in request body', 400)

        except Exception as e:
            logger.exception(f"Error stopping simulator: {e}")
            span.record_exception(e)
            track_simulator_operation("stop", "error_exception")
            return create_error_response('Server error during simulator stop', 500)
