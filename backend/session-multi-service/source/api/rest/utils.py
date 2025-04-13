# source/api/rest/utils.py
"""
REST API utility functions.
"""
import logging
from typing import Tuple, Optional, Dict, Any
from aiohttp import web

from source.api.utils import get_token_from_request, validate_token_with_auth_service

logger = logging.getLogger('rest_utils')


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

    # Validate token directly with auth service
    validation = await validate_token_with_auth_service(token)

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


def create_error_response(error: str, status: int = 400) -> web.Response:
    """Create a standard error response"""
    return web.json_response({
        'success': False,
        'error': error
    }, status=status)
