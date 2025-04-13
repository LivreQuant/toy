# source/api/websocket/utils.py
"""
WebSocket utility functions.
Simplified for singleton session mode.
"""
import logging
from typing import Tuple, Any

from aiohttp import web

from source.core.session.manager import SessionManager
from source.api.utils import validate_token_with_auth_service
from source.api.websocket.exceptions import (
    WebSocketClientError,
    AuthenticationError,
    WebSocketServerError
)

logger = logging.getLogger('websocket_utils')


async def authenticate_websocket_request(
        request: web.Request,
        session_manager: SessionManager
) -> Tuple[Any, str, str]:
    """
    Authenticates a WebSocket connection request in singleton mode.
    
    In singleton mode, we still validate the token but always use the 
    pre-initialized session.

    Args:
        request: The incoming aiohttp request object.
        session_manager: The session manager instance for direct access.

    Returns:
        A tuple containing: (user_id, session_id, device_id)

    Raises:
        WebSocketClientError: If required parameters are missing or invalid input.
        AuthenticationError: If the token is invalid.
        WebSocketServerError: If session validation fails unexpectedly.
    """
    query = request.query
    token = query.get('token')
    device_id = query.get('deviceId', 'default-device')

    # 1. Validate required parameters
    if not token:
        logger.warning("Authentication failed: Missing token query parameter")
        raise WebSocketClientError(
            message="Missing required parameter: token",
            error_code="MISSING_PARAMETERS"
        )

    # 2. In singleton mode, get the session ID from the session manager
    if session_manager.singleton_mode:
        session_id = session_manager.singleton_session_id
        
        # Validate token but don't enforce user matching
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
        
        # In singleton mode, we don't validate that the user matches the session
        logger.info(f"Using singleton session {session_id} for user {user_id}, device {device_id}")
        return user_id, session_id, device_id
    else:
        # Original multi-user authentication would go here
        raise NotImplementedError("Multi-user mode authentication not implemented")
    