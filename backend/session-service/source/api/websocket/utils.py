# source/api/websocket/utils.py
"""
WebSocket utility functions.
Simplified for single-user mode.
"""
import logging
from typing import Tuple, Any

from aiohttp import web

from source.core.session.manager import SessionManager
from source.api.utils import validate_token_with_auth_service
from source.api.websocket.exceptions import (
    WebSocketClientError,
    AuthenticationError,
)

logger = logging.getLogger('websocket_utils')


async def authenticate_websocket_request(
        request: web.Request,
        session_manager: SessionManager
) -> Tuple[Any, str, str]:
    """
    Authenticates a WebSocket connection request for a single-user service.

    Args:
        request: The incoming aiohttp request object.
        session_manager: The session manager instance.

    Returns:
        A tuple containing: (user_id, session_id, device_id)

    Raises:
        WebSocketClientError: If required parameters are missing.
        AuthenticationError: If the token is invalid.
    """
    query = request.query
    token = query.get('token')
    device_id = query.get('deviceId', 'default-device')

    # Validate required parameters
    if not token:
        logger.warning("Authentication failed: Missing token query parameter")
        raise WebSocketClientError(
            message="Missing required parameter: token",
            error_code="MISSING_PARAMETERS"
        )

    # Get the session ID (in single-user mode, it's pre-defined)
    session_id = session_manager.session_id

    # Validate token
    validation_result = await validate_token_with_auth_service(token)

    if not validation_result.get('valid', False):
        logger.warning(f"Authentication failed: Invalid token for device {device_id}")
        raise AuthenticationError(
            message="Invalid authentication token",
        )

    user_id = validation_result.get('userId')

    if not user_id:
        logger.warning(f"Authentication failed: No user ID in token for device {device_id}")
        raise AuthenticationError(
            message="Invalid authentication token - missing user ID",
        )

    # In single-user mode, we don't validate that the user matches the session
    logger.info(f"WebSocket authenticated for user {user_id}, device {device_id}, session {session_id}")

    # Update the session metadata with the device ID
    await session_manager.update_session_metadata({
        'device_id': device_id
    })

    return user_id, session_id, device_id
