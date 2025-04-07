"""
Simplified REST API request handlers.
Implements the handlers for the core session and simulator control endpoints.
"""
import logging
import json
import time
from aiohttp import web
from opentelemetry import trace

from source.utils.metrics import track_rest_request
from source.utils.tracing import optional_trace_span

logger = logging.getLogger('rest_handlers')
_tracer = trace.get_tracer("rest_handlers")

# --- Helper to get token ---
async def get_token_from_request(request):
    """Extract token from Authorization header."""
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header[7:]
    return None

# --- Session Handlers ---

async def handle_create_session(request):
    """
    Handle session creation request.

    Args:
        request: HTTP request

    Returns:
        JSON response with sessionId.
    """
    with optional_trace_span(_tracer, "handle_create_session") as span:
        session_manager = request.app['session_manager']
        start_time = time.time()
        try:
            data = await request.json()
            device_id = data.get('deviceId')
            span.set_attribute("app.device_id", device_id)

            if not device_id:
                span.set_attribute("error.message", "Missing deviceId")
                track_rest_request('POST', 'create_session', 400, time.time() - start_time)
                return web.json_response({'success': False, 'error': 'Missing deviceId'}, status=400)

            token = await get_token_from_request(request)
            span.set_attribute("app.has_token", token is not None)
            if not token:
                span.set_attribute("error.message", "Missing Authorization token")
                track_rest_request('POST', 'create_session', 401, time.time() - start_time)
                return web.json_response({'success': False, 'error': 'Missing Authorization token'}, status=401)

            # Validate token and get user ID
            token_validation = await session_manager.auth_client.validate_token(token)
            if not token_validation.get('valid', False):
                span.set_attribute("error.message", "Invalid token")
                track_rest_request('POST', 'create_session', 401, time.time() - start_time)
                return web.json_response({'success': False, 'error': 'Invalid token'}, status=401)

            user_id = token_validation.get('userId')
            span.set_attribute("app.user_id", user_id)
            if not user_id:
                span.set_attribute("error.message", "User ID not found in token")
                track_rest_request('POST', 'create_session', 401, time.time() - start_time)
                return web.json_response({'success': False, 'error': 'User ID not found in token'}, status=401)

            client_ip = request.remote
            span.set_attribute("net.peer.ip", client_ip)

            # Create session
            session_id, is_new = await session_manager.create_session(user_id, device_id, token, client_ip)

            if not session_id:
                 span.set_attribute("error.message", "Failed to create session")
                 track_rest_request('POST', 'create_session', 500, time.time() - start_time)
                 return web.json_response({'success': False, 'error': 'Failed to create session'}, status=500)

            span.set_attribute("app.session_id", session_id)
            span.set_attribute("app.is_new", is_new)
            track_rest_request('POST', 'create_session', 200, time.time() - start_time)
            # Return only session ID as per simplification (isNew might be internal detail)
            return web.json_response({'success': True, 'sessionId': session_id})

        except json.JSONDecodeError:
            span.set_attribute("error.message", "Invalid JSON")
            track_rest_request('POST', 'create_session', 400, time.time() - start_time)
            return web.json_response({'success': False, 'error': 'Invalid JSON in request body'}, status=400)
        except Exception as e:
            logger.error(f"Error creating session: {e}", exc_info=True)
            span.record_exception(e)
            track_rest_request('POST', 'create_session', 500, time.time() - start_time)
            return web.json_response({'success': False, 'error': 'Server error'}, status=500)

async def handle_end_session(request):
    """
    Handle session termination request.

    Args:
        request: HTTP request

    Returns:
        JSON response indicating success or failure.
    """
    with optional_trace_span(_tracer, "handle_end_session") as span:
        session_manager = request.app['session_manager']
        start_time = time.time()
        try:
            # End session requires sessionId and token, typically from request body or query/path
            # Assuming body for DELETE based on previous structure
            data = await request.json()
            session_id = data.get('sessionId')
            token = data.get('token') # Or get from Auth header
            span.set_attribute("app.session_id", session_id)
            span.set_attribute("app.has_token", token is not None)

            if not session_id or not token:
                 span.set_attribute("error.message", "Missing sessionId or token")
                 track_rest_request('DELETE', 'end_session', 400, time.time() - start_time)
                 return web.json_response({'success': False, 'error': 'Missing sessionId or token'}, status=400)

            # End session using SessionManager
            success, error = await session_manager.end_session(session_id, token)

            if not success:
                status_code = 401 if "Invalid session or token" in error else 400 # Or 500 for server errors
                span.set_attribute("error.message", error)
                track_rest_request('DELETE', 'end_session', status_code, time.time() - start_time)
                return web.json_response({'success': False, 'error': error}, status=status_code)

            track_rest_request('DELETE', 'end_session', 200, time.time() - start_time)
            return web.json_response({'success': True})

        except json.JSONDecodeError:
            span.set_attribute("error.message", "Invalid JSON")
            track_rest_request('DELETE', 'end_session', 400, time.time() - start_time)
            return web.json_response({'success': False, 'error': 'Invalid JSON in request body'}, status=400)
        except Exception as e:
            logger.error(f"Error ending session {session_id}: {e}", exc_info=True)
            span.record_exception(e)
            track_rest_request('DELETE', 'end_session', 500, time.time() - start_time)
            return web.json_response({'success': False, 'error': 'Server error'}, status=500)

# --- Simulator Handlers ---

async def handle_start_simulator(request):
    """
    Handle simulator start request.

    Args:
        request: HTTP request

    Returns:
        JSON response indicating success or failure.
    """
    with optional_trace_span(_tracer, "handle_start_simulator") as span:
        session_manager = request.app['session_manager']
        start_time = time.time()
        try:
            token = await get_token_from_request(request)
            span.set_attribute("app.has_token", token is not None)
            if not token:
                span.set_attribute("error.message", "Missing Authorization token")
                track_rest_request('GET', 'start_simulator', 401, time.time() - start_time)
                return web.json_response({'success': False, 'error': 'Missing Authorization token'}, status=401)

            # Session ID from query parameter
            session_id = request.query.get('sessionId')
            span.set_attribute("app.session_id", session_id)
            if not session_id:
                span.set_attribute("error.message", "Missing sessionId parameter")
                track_rest_request('GET', 'start_simulator', 400, time.time() - start_time)
                return web.json_response({'success': False, 'error': 'Missing sessionId parameter'}, status=400)

            # Optional symbols from query parameter
            symbols_param = request.query.get('symbols', '')
            symbols = symbols_param.split(',') if symbols_param else None # Pass None if empty
            span.set_attribute("app.symbols", symbols or [])

            # Start simulator using SessionManager
            # Returns (simulator_id, endpoint, error_message) - we only care about error here
            _, _, error = await session_manager.start_simulator(session_id, token, symbols)

            if error:
                # Determine appropriate status code
                status_code = 400
                if "Invalid session" in error:
                     status_code = 401
                elif "limit reached" in error or "in progress" in error:
                     status_code = 409 # Conflict
                elif "Failed to create" in error or "Server error" in error:
                     status_code = 500

                span.set_attribute("error.message", error)
                track_rest_request('GET', 'start_simulator', status_code, time.time() - start_time)
                return web.json_response({'success': False, 'error': error}, status=status_code)

            # Return simple success, status is communicated via WebSocket
            track_rest_request('GET', 'start_simulator', 200, time.time() - start_time)
            return web.json_response({'success': True, 'message': 'Simulator start initiated'})

        except Exception as e:
            logger.error(f"Error starting simulator for session {session_id}: {e}", exc_info=True)
            span.record_exception(e)
            track_rest_request('GET', 'start_simulator', 500, time.time() - start_time)
            return web.json_response({'success': False, 'error': 'Server error'}, status=500)

async def handle_stop_simulator(request):
    """
    Handle simulator stop request.

    Args:
        request: HTTP request

    Returns:
        JSON response indicating success or failure.
    """
    with optional_trace_span(_tracer, "handle_stop_simulator") as span:
        session_manager = request.app['session_manager']
        start_time = time.time()
        try:
            # Stop simulator requires sessionId and token
            # Assuming body for DELETE based on previous structure
            data = await request.json()
            session_id = data.get('sessionId')
            token = data.get('token') # Or get from Auth header
            span.set_attribute("app.session_id", session_id)
            span.set_attribute("app.has_token", token is not None)

            if not session_id or not token:
                 span.set_attribute("error.message", "Missing sessionId or token")
                 track_rest_request('DELETE', 'stop_simulator', 400, time.time() - start_time)
                 return web.json_response({'success': False, 'error': 'Missing sessionId or token'}, status=400)

            # Stop simulator using SessionManager
            success, error = await session_manager.stop_simulator(session_id, token)

            if not success:
                status_code = 400
                if "Invalid session" in error:
                     status_code = 401
                elif "No active simulator" in error:
                     status_code = 404 # Not found
                elif "Server error" in error:
                     status_code = 500

                span.set_attribute("error.message", error)
                track_rest_request('DELETE', 'stop_simulator', status_code, time.time() - start_time)
                return web.json_response({'success': False, 'error': error}, status=status_code)

            # Return simple success, status is communicated via WebSocket
            track_rest_request('DELETE', 'stop_simulator', 200, time.time() - start_time)
            return web.json_response({'success': True, 'message':