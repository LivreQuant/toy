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
from source.api.rest.utils import get_token_from_request

logger = logging.getLogger('simulator_handlers')  # Updated logger name
_tracer = trace.get_tracer("simulator_handlers")  # Updated tracer name


async def handle_start_simulator(request):
    """
    Handle simulator start request.
    Requires sessionId in query params and token in Authorization header.

    Args:
        request: HTTP request

    Returns:
        JSON response
    """
    with optional_trace_span(_tracer, "handle_start_simulator") as span:
        # Assume session_manager holds or provides access to simulator_manager
        session_manager = request.app['session_manager']

        try:
            # Get token from Authorization header
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                span.set_attribute("error", "Missing or invalid Authorization header")
                return web.json_response({
                    'success': False,
                    'error': 'Missing or invalid Authorization header'
                }, status=401)

            token = await get_token_from_request(request)
            span.set_attribute("has_token", True)

            # Extract user ID from token
            validation = await session_manager.auth_client.validate_token(token)
            if not validation.get('valid', False):
                return web.json_response({
                    'success': False,
                    'error': 'Invalid authentication token'
                }, status=401)

            user_id = validation.get('userId')
            if not user_id:
                return web.json_response({
                    'success': False,
                    'error': 'User ID not found in token'
                }, status=401)

            # Get active session for user (or create one if needed)
            active_sessions = await session_manager.db_manager.get_active_user_sessions(user_id)

            # Use the first active session (assuming one user has one primary active session)
            session = active_sessions[0]
            session_id = session.session_id

            # Start simulator (session validation should happen inside start_simulator)
            # start_simulator should return: (simulator_id, endpoint, error_message)
            simulator_id, endpoint, error = await session_manager.start_simulator(session_id, token)
            span.set_attribute("start_error", error)
            span.set_attribute("simulator_id", simulator_id)

            if error:
                # Determine status code based on error
                status = 400  # Default bad request
                if "Invalid session or token" in error or "ownership" in error:
                    status = 401
                elif "not found" in error:
                    status = 404
                elif "already running" in error or "limit reached" in error:
                    status = 409  # Conflict
                track_simulator_operation("start")
                return web.json_response({
                    'success': False,
                    'error': error
                }, status=status)

            track_simulator_operation("start")
            return web.json_response({
                'success': True,
                'status': 'STARTING',  # Indicate async start
            })

        except Exception as e:
            logger.exception(f"Error starting simulator: {e}")
            span.record_exception(e)
            track_simulator_operation("start")
            return web.json_response({
                'success': False,
                'error': 'Server error during simulator start'
            }, status=500)


async def handle_stop_simulator(request):
    """
    Handle simulator stop request using sessionId and token from JSON body.
    Does not require simulator_id in the request.

    Args:
        request: HTTP request

    Returns:
        JSON response
    """
    with optional_trace_span(_tracer, "handle_stop_simulator") as span:
        session_manager = request.app['session_manager']

        try:
            # Get token from Authorization header
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return web.json_response({
                    'success': False,
                    'error': 'Missing authorization token'
                }, status=401)

            token = await get_token_from_request(request)
            span.set_attribute("has_token", True)

            # Extract user ID from token
            validation = await session_manager.auth_client.validate_token(token)
            if not validation.get('valid', False):
                return web.json_response({
                    'success': False,
                    'error': 'Invalid authentication token'
                }, status=401)

            user_id = validation.get('userId')
            if not user_id:
                return web.json_response({
                    'success': False,
                    'error': 'User ID not found in token'
                }, status=401)

            # Get active session for user
            active_sessions = await session_manager.db_manager.get_active_user_sessions(user_id)

            if not active_sessions:
                return web.json_response({
                    'success': False,
                    'error': 'No active session found'
                }, status=404)

            # Use the first active session
            session = active_sessions[0]
            session_id = session.session_id

            # Stop simulator associated with this session
            success, error = await session_manager.stop_simulator(session_id, token)

            span.set_attribute("stop_success", success)

            if not success:
                span.set_attribute("error", error)
                # Determine status code based on error
                status = 400  # Default
                if "Invalid session or token" in error or "ownership" in error:
                    status = 401
                elif "not found" in error or "no simulator" in error:
                    # Consider if "no simulator" is an error or success (idempotency)
                    # If idempotent, maybe return success=True? For now, treat as error.
                    status = 404
                track_simulator_operation("stop")
                return web.json_response({
                    'success': False,
                    'error': error
                }, status=status)

            track_simulator_operation("stop")
            return web.json_response({'success': True})

        except json.JSONDecodeError:
            logger.warning("Invalid JSON received for stop simulator.")
            span.set_attribute("error", "Invalid JSON in request body")
            return web.json_response({
                'success': False,
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            logger.exception(f"Error stopping simulator: {e}")
            span.record_exception(e)
            track_simulator_operation("stop")
            return web.json_response({
                'success': False,
                'error': 'Server error during simulator stop'
            }, status=500)
