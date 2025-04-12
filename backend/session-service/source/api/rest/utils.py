# source/api/rest/utils.py
"""
REST API utility functions.
"""
import json
import logging
from typing import Tuple, Optional, Dict, Any
from aiohttp import web

logger = logging.getLogger('rest_utils')


async def get_token_from_request(request):
    """
    Extract token from request headers, query parameters, or JSON body.

    Priority:
    1. Authorization: Bearer <token> header
    2. 'token' query parameter
    3. 'token' field in JSON body (if applicable)

    Args:
        request: The aiohttp web request object.

    Returns:
        The extracted token string, or None if not found.
    """
    # 1. Try Authorization header
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header[7:]

    # 2. Try query parameter
    token = request.query.get('token')
    if token:
        return token

    # 3. Try POST body (for JSON requests)
    content_type = request.headers.get('Content-Type', '')
    # Check if body exists and content type suggests JSON before attempting read/parse
    if request.can_read_body and 'application/json' in content_type:
        try:
            # Use await request.json() which handles parsing
            data = await request.json()
            if isinstance(data, dict) and 'token' in data:
                return data['token']
        except json.JSONDecodeError:
            # Ignore if body is not valid JSON
            pass
        except Exception:
            # Log other potential errors if needed, but generally ignore for token extraction
            pass  # E.g. reading body fails for some reason

    return None


async def validate_auth_token(request, span=None) -> Tuple[
    Optional[str], Optional[Dict[str, Any]], Optional[web.Response]]:
    """
    Validate authentication token and extract user ID.

    Args:
        request: The HTTP request
        span: Optional tracing span

    Returns:
        Tuple of (user_id, validation_result, error_response)
        If validation fails, user_id and validation_result will be None, and error_response will contain
        a web.Response object with the appropriate error.
        If validation succeeds, error_response will be None.
    """
    # Get session manager
    session_manager = request.app['session_manager']

    # Get token from request (any location)
    token = await get_token_from_request(request)
    if span:
        span.set_attribute("has_token", token is not None)

    if not token:
        logger.warning("Missing authorization token in request")
        return None, None, web.json_response({
            'success': False,
            'error': 'Missing authorization token'
        }, status=401)

    # Validate token with auth service
    validation = await session_manager.auth_client.validate_token(token)

    if not validation.get('valid', False):
        logger.warning(f"Invalid token validation result: {validation}")
        return None, None, web.json_response({
            'success': False,
            'error': 'Invalid authentication token'
        }, status=401)

    user_id = validation.get('userId')
    if span:
        span.set_attribute("user_id", user_id)

    if not user_id:
        logger.warning("Token validation succeeded but no userId returned")
        return None, None, web.json_response({
            'success': False,
            'error': 'User ID not found in token'
        }, status=401)

    return user_id, validation, None


async def get_active_session(request, user_id: str, token: str, span=None) -> Tuple[
    Optional[Any], Optional[web.Response]]:
    """
    Get the active session for a user.

    Args:
        request: The HTTP request
        user_id: The user ID
        token: Auth token
        span: Optional tracing span

    Returns:
        Tuple of (session, error_response)
        If there's an error, session will be None and error_response will contain
        a web.Response object with the appropriate error.
        If successful, error_response will be None.
    """
    session_manager = request.app['session_manager']

    # Get active session for user
    logger.info(f"Attempting to get active sessions for user: {user_id}")
    active_sessions = await session_manager.db_manager.get_active_user_sessions(user_id)
    logger.info(f"Found {len(active_sessions)} active sessions for user {user_id}")

    if not active_sessions:
        return None, web.json_response({
            'success': False,
            'error': 'No active session found'
        }, status=404)

    # Use the first active session
    session = active_sessions[0]
    if span:
        span.set_attribute("session_id", session.session_id)

    return session, None


def create_error_response(error: str, status: int = 400) -> web.Response:
    """Create a standard error response"""
    return web.json_response({
        'success': False,
        'error': error
    }, status=status)
