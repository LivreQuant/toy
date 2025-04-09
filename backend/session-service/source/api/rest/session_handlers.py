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
from source.api.rest.utils import get_token_from_request

logger = logging.getLogger('session_handlers')  # Updated logger name
_tracer = trace.get_tracer("session_handlers")  # Updated tracer name


async def handle_create_session(request):
    """
    Handle session creation request with deviceId in request body
    and user info from Authorization header.

    Args:
        request: HTTP request

    Returns:
        JSON response
    """
    with optional_trace_span(_tracer, "handle_create_session") as span:
        session_manager = request.app['session_manager']

        try:
            # Log the raw request (optional, consider privacy implications)
            # body = await request.text()
            # logger.info(f"Received session creation request: {body}") # Consider logging level

            # Parse request body
            data = await request.json()
            logger.debug(f"Parsed session creation request data: {data}")  # Use debug level

            # Extract deviceId from request
            device_id = data.get('deviceId')
            span.set_attribute("device_id", device_id)

            if not device_id:
                span.set_attribute("error", "Missing deviceId")
                return web.json_response({
                    'success': False,
                    'error': 'Missing deviceId'
                }, status=400)

            # Get token from Authorization header
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                span.set_attribute("error", "Missing or invalid Authorization header")
                return web.json_response({
                    'success': False,
                    'error': 'Missing or invalid Authorization header'
                }, status=401)

            token = auth_header[7:]  # Remove 'Bearer ' prefix
            span.set_attribute("has_token", True)

            # Validate token and extract user ID
            # Assume auth_client is accessible via session_manager or app context
            auth_client = getattr(session_manager, 'auth_client', request.app.get('auth_client'))
            if not auth_client:
                logger.error("Auth client not configured.")
                span.set_attribute("error", "Auth client configuration error")
                return web.json_response({'success': False, 'error': 'Server configuration error'}, status=500)

            token_validation = await auth_client.validate_token(token)
            logger.info(f"Token validation result for create session: {token_validation}")

            if not token_validation.get('valid', False):
                span.set_attribute("error", "Invalid token")
                return web.json_response({
                    'success': False,
                    'error': 'Invalid token'
                }, status=401)

            user_id = token_validation.get('userId')
            span.set_attribute("user_id", user_id)

            if not user_id:
                span.set_attribute("error", "User ID not found in token")
                return web.json_response({
                    'success': False,
                    'error': 'User ID not found in token'
                }, status=401)

            # Get client IP (ensure proxy setup is handled if applicable)
            client_ip = request.remote
            span.set_attribute("client_ip", client_ip)

            # Create session with device_id
            session_id, is_new = await session_manager.create_session(user_id, device_id, token, client_ip)

            if not session_id:
                span.set_attribute("error", "Session creation failed")
                track_session_operation("create")
                return web.json_response({
                    'success': False,
                    'error': 'Failed to create session'
                }, status=500)

            span.set_attribute("session_id", session_id)
            span.set_attribute("is_new", is_new)
            track_session_operation("create")
            return web.json_response({
                'success': True,
                'sessionId': session_id,  # Return sessionId for client use
                'isNew': is_new
            })

        except json.JSONDecodeError:
            logger.warning("Invalid JSON received for create session.")
            span.set_attribute("error", "Invalid JSON in request body")
            return web.json_response({
                'success': False,
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            logger.exception(f"Error creating session: {e}")  # Use exception logging
            span.record_exception(e)
            track_session_operation("create")
            return web.json_response({
                'success': False,
                'error': 'Server error during session creation'
            }, status=500)


async def handle_get_session(request):
    """
    Handle session retrieval request using session_id from path and token.
    Note: This assumes a route like GET /api/sessions/{session_id} exists.
          The provided setup_rest_routes doesn't include this.
          handle_get_session_state might be the intended handler for state checks.

    Args:
        request: HTTP request

    Returns:
        JSON response
    """
    with optional_trace_span(_tracer, "handle_get_session") as span:
        session_manager = request.app['session_manager']

        # Get session ID from URL path
        session_id = request.match_info.get('session_id')
        if not session_id:
            return web.json_response({'success': False, 'error': 'Missing session_id in path'}, status=400)
        span.set_attribute("session_id", session_id)

        # Get token using the utility function
        token = await get_token_from_request(request)
        span.set_attribute("has_token", token is not None)

        if not token:
            span.set_attribute("error", "Missing authentication token")
            return web.json_response({
                'success': False,
                'error': 'Missing authentication token'
            }, status=401)

        # Validate session ownership using the token
        user_id = await session_manager.validate_session(session_id, token)
        span.set_attribute("user_id", user_id)
        span.set_attribute("session_valid", user_id is not None)

        if not user_id:
            # Differentiate between not found and invalid token/session
            session_exists = await session_manager.session_exists(session_id)  # Assumes this method exists
            if session_exists:
                span.set_attribute("error", "Invalid token for session")
                status = 401
                error_msg = 'Invalid token for session'
            else:
                span.set_attribute("error", "Session not found")
                status = 404
                error_msg = 'Session not found'
            track_session_operation("get")
            return web.json_response({'success': False, 'error': error_msg}, status=status)

        # Get full session details
        session = await session_manager.get_session(session_id)
        span.set_attribute("session_found", session is not None)  # Should always be true if validated

        if not session:  # Should technically not happen if validation passed, but good practice
            span.set_attribute("error", "Session not found after validation")
            track_session_operation("get")
            return web.json_response({
                'success': False,
                'error': 'Session disappeared unexpectedly'
            }, status=404)

        # Return session details
        track_session_operation("get")
        return web.json_response({
            'success': True,
            'session': session  # Consider filtering sensitive data before returning
        })


async def handle_get_session_state(request):
    """
    Handle session state request to get limited info like simulator status.
    Uses query parameters for sessionId and token.

    Args:
        request: HTTP request

    Returns:
        JSON response with session state
    """
    with optional_trace_span(_tracer, "handle_get_session_state") as span:
        session_manager = request.app['session_manager']

        # Get session ID and token from query params
        session_id = request.query.get('sessionId')
        token = request.query.get('token')  # Or use await get_token_from_request(request) for consistency

        span.set_attribute("session_id", session_id)
        span.set_attribute("has_token", token is not None)

        if not session_id or not token:
            span.set_attribute("error", "Missing sessionId or token in query")
            return web.json_response({
                'success': False,
                'error': 'Missing sessionId or token query parameter'
            }, status=400)

        # Validate session ownership using the token
        user_id = await session_manager.validate_session(session_id, token)
        span.set_attribute("user_id", user_id)
        span.set_attribute("session_valid", user_id is not None)

        if not user_id:
            # Similar check as handle_get_session for better error reporting
            session_exists = await session_manager.session_exists(session_id)
            if session_exists:
                span.set_attribute("error", "Invalid token for session state")
                status = 401
                error_msg = 'Invalid token for session'
            else:
                span.set_attribute("error", "Session not found for state check")
                status = 404
                error_msg = 'Session not found'
            track_session_operation("get_state")
            return web.json_response({'success': False, 'error': error_msg}, status=status)

        # Get session details needed for the state response
        session = await session_manager.get_session(session_id)  # Could potentially get only metadata if optimized
        span.set_attribute("session_found", session is not None)

        if not session:
            span.set_attribute("error", "Session not found after validation (state check)")
            track_session_operation("get_state")
            return web.json_response({
                'success': False,
                'error': 'Session disappeared unexpectedly'
            }, status=404)

        # Extract relevant state info
        metadata = session.get('metadata', {}) if isinstance(session.get('metadata'), dict) else {}
        simulator_id = metadata.get('simulator_id')
        simulator_status = metadata.get('simulator_status', 'UNKNOWN')

        response_data = {
            'success': True,
            'sessionId': session_id,
            'sessionCreatedAt': session.get('created_at', 0),  # Consider formatting as ISO string
            'lastActive': session.get('last_active', 0),  # Consider formatting as ISO string
            'simulatorId': simulator_id,
            'simulatorStatus': simulator_status,
        }

        track_session_operation("get_state")
        return web.json_response(response_data)


async def handle_end_session(request):
    """
    Handle session termination request using sessionId and token from JSON body.

    Args:
        request: HTTP request

    Returns:
        JSON response
    """
    with optional_trace_span(_tracer, "handle_end_session") as span:
        session_manager = request.app['session_manager']

        try:
            # Parse request body
            data = await request.json()
            logger.debug(f"Parsed end session request data: {data}")

            # Extract parameters
            session_id = data.get('sessionId')
            # Use get_token_from_request or get from body explicitly
            token = data.get('token')  # Assuming token is passed in body here

            span.set_attribute("session_id", session_id)
            span.set_attribute("has_token", token is not None)

            if not session_id or not token:
                span.set_attribute("error", "Missing sessionId or token in body")
                return web.json_response({
                    'success': False,
                    'error': 'Missing sessionId or token in request body'
                }, status=400)

            # End session (validation happens inside end_session)
            success, error = await session_manager.end_session(session_id, token)
            span.set_attribute("end_success", success)

            if not success:
                span.set_attribute("error", error)
                # Determine status code based on error (e.g., 401/403 for auth, 404 not found, 400 bad request)
                status = 400  # Default
                if "Invalid session or token" in error or "ownership" in error:
                    status = 401  # Or 403 Forbidden
                elif "not found" in error:
                    status = 404

                track_session_operation("end")
                return web.json_response({
                    'success': False,
                    'error': error
                }, status=status)

            track_session_operation("end")
            return web.json_response({'success': True})

        except json.JSONDecodeError:
            logger.warning("Invalid JSON received for end session.")
            span.set_attribute("error", "Invalid JSON in request body")
            return web.json_response({
                'success': False,
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            logger.exception(f"Error ending session: {e}")
            span.record_exception(e)
            track_session_operation("end")
            return web.json_response({
                'success': False,
                'error': 'Server error during session termination'
            }, status=500)


async def handle_session_ready(request):
    """
    Session readiness check endpoint.
    Uses session_id from path and token from query param.

    Args:
        request: HTTP request

    Returns:
        JSON response indicating if session is valid/ready.
    """
    with optional_trace_span(_tracer, "handle_session_ready") as span:
        session_manager = request.app['session_manager']

        # Get session ID from URL path
        session_id = request.match_info.get('session_id')
        if not session_id:
            return web.json_response(
                {'success': False, 'status': 'bad_request', 'message': 'Missing session_id in path'}, status=400)
        span.set_attribute("session_id", session_id)

        # Get token from query params
        token = request.query.get('token')  # Or use await get_token_from_request(request)
        span.set_attribute("has_token", token is not None)

        if not token:
            span.set_attribute("error", "Missing token")
            return web.json_response({
                'success': False,
                'status': 'unauthorized',
                'message': 'Missing token query parameter'
            }, status=401)

        # Validate session ownership
        user_id = await session_manager.validate_session(session_id, token)
        span.set_attribute("user_id", user_id)
        span.set_attribute("session_valid", user_id is not None)

        if not user_id:
            session_exists = await session_manager.session_exists(session_id)
            if session_exists:
                span.set_attribute("error", "Invalid token for readiness check")
                status_code = 401
                status_msg = 'invalid'
                message = 'Invalid token for session'
            else:
                span.set_attribute("error", "Session not found for readiness check")
                status_code = 404
                status_msg = 'not_found'
                message = 'Session not found'
            track_session_operation("ready_check")
            return web.json_response({
                'success': False,
                'status': status_msg,
                'message': message
            }, status=status_code)

        # If validation passes, the session is considered ready/valid
        # Optionally, could add more checks here (e.g., check session state flags)
        track_session_operation("ready_check")
        return web.json_response({
            'success': True,
            'status': 'ready',
            'message': 'Session is valid and ready for connection'
        })


async def handle_reconnect_session(request):
    """
    Handle session reconnection request using sessionId, deviceId from body
    and token from Authorization header.

    Args:
        request: HTTP request

    Returns:
        JSON response with session data if successful.
    """
    with optional_trace_span(_tracer, "handle_reconnect_session") as span:
        session_manager = request.app['session_manager']

        try:
            # Parse request body
            data = await request.json()
            logger.debug(f"Parsed reconnect session request data: {data}")

            # Extract parameters from body
            session_id = data.get('sessionId')
            device_id = data.get('deviceId')
            attempt = data.get('attempt', 1)  # Optional attempt number

            span.set_attribute("session_id", session_id)
            span.set_attribute("device_id", device_id)
            span.set_attribute("reconnect_attempt", attempt)

            if not session_id or not device_id:
                span.set_attribute("error", "Missing sessionId or deviceId in body")
                return web.json_response({
                    'success': False,
                    'error': 'Missing sessionId or deviceId in request body'
                }, status=400)

            # Get token from Authorization header
            # Could also use get_token_from_request if header isn't mandatory
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                span.set_attribute("error", "Missing or invalid Authorization header")
                return web.json_response({
                    'success': False,
                    'error': 'Missing or invalid Authorization header'
                }, status=401)

            token = auth_header[7:]  # Remove 'Bearer ' prefix
            span.set_attribute("has_token", True)

            # Attempt to reconnect to session (validation is part of reconnect logic)
            session_data, error = await session_manager.reconnect_session(session_id, token, device_id, attempt)
            span.set_attribute("reconnect_success", error is None)

            if error:
                span.set_attribute("error", error)
                # Determine status code based on error
                status = 400  # Default
                if "Invalid" in error or "ownership" in error or "token" in error:
                    status = 401  # Or 403
                elif "not found" in error:
                    status = 404
                elif "mismatch" in error:
                    status = 409  # Conflict? Or 400 Bad Request
                track_session_operation("reconnect")
                return web.json_response({
                    'success': False,
                    'error': error
                }, status=status)

            track_session_operation("reconnect")
            # Return sensitive data carefully
            return web.json_response({
                'success': True,
                'session': session_data  # Ensure this doesn't leak sensitive info
            })

        except json.JSONDecodeError:
            logger.warning("Invalid JSON received for reconnect session.")
            span.set_attribute("error", "Invalid JSON in request body")
            return web.json_response({
                'success': False,
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            logger.exception(f"Error reconnecting session: {e}")
            span.record_exception(e)
            track_session_operation("reconnect")
            return web.json_response({
                'success': False,
                'error': 'Server error during session reconnection'
            }, status=500)
