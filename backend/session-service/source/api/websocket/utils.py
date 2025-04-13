# source/api/websocket/utils.py
"""
WebSocket utility functions.
Enhanced for device ID validation and connection management.
"""
import logging
import time
from typing import Tuple, Any

from aiohttp import web

from source.core.session.manager import SessionManager
from source.api.utils import validate_token_with_auth_service
from source.api.websocket.exceptions import (
    WebSocketClientError,
    AuthenticationError,
    DeviceMismatchError,
    ConnectionLimitError
)

logger = logging.getLogger('websocket_utils')


async def authenticate_websocket_request(
        request: web.Request,
        session_manager: SessionManager
) -> Tuple[Any, str, str]:
    """
    Authenticates a WebSocket connection request for a single-user service.
    Enhanced with device ID validation.

    Args:
        request: The incoming aiohttp request object.
        session_manager: The session manager instance.

    Returns:
        A tuple containing: (user_id, session_id, device_id)

    Raises:
        WebSocketClientError: If required parameters are missing.
        AuthenticationError: If the token is invalid.
        DeviceMismatchError: If a different device ID is active for this user.
        ConnectionLimitError: If maximum connections are reached.
    """
    query = request.query
    token = query.get('token')
    device_id = query.get('deviceId')

    # Validate required parameters
    if not token:
        logger.warning("Authentication failed: Missing token query parameter")
        raise WebSocketClientError(
            message="Missing required parameter: token",
            error_code="MISSING_PARAMETERS"
        )
        
    if not device_id:
        logger.warning("Authentication failed: Missing deviceId query parameter")
        raise WebSocketClientError(
            message="Missing required parameter: deviceId",
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

    # Check if device ID matches existing session
    session = await session_manager.get_session()
    
    if not session:
        logger.warning(f"Session {session_id} not found during WebSocket authentication")
        raise WebSocketClientError(
            message="Session not found",
            error_code="SESSION_NOT_FOUND"
        )
        
    metadata = session.metadata if session else None
    existing_device_id = metadata.device_id if metadata else None
    
    if existing_device_id and existing_device_id != device_id:
        logger.warning(f"Device mismatch: User {user_id} attempting connection with device {device_id}, " 
                      f"but session is active on device {existing_device_id}")
        raise DeviceMismatchError(
            message="Session already active on another device",
            expected=existing_device_id,
            received=device_id
        )

    logger.info(f"WebSocket authenticated for user {user_id}, device {device_id}, session {session_id}")

    # Update the session metadata with the device ID and connection timestamp
    await session_manager.update_session_metadata({
        'device_id': device_id,
        'last_connection': time.time(),
        'user_agent': request.headers.get('User-Agent', 'unknown'),
        'ip_address': request.remote
    })

    return user_id, session_id, device_id


async def validate_message_params(message: dict, required_params: list) -> Tuple[bool, str]:
    """
    Validates that a message contains all required parameters.
    
    Args:
        message: The message to validate
        required_params: List of required parameter names
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    for param in required_params:
        if param not in message:
            return False, f"Missing required parameter: {param}"
        
        # Also check for empty string values
        if message[param] == "" and param != "requestId":  # requestId can be empty
            return False, f"Empty value for required parameter: {param}"
            
    return True, ""
