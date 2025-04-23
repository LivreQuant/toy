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
    WebSocketError,  # Keep this import
    ClientError,  # Import the new name instead of WebSocketClientError
)

logger = logging.getLogger('websocket_utils')


async def authenticate_websocket_request(
        request: web.Request,
        session_manager: SessionManager
) -> Tuple[Any, str]:
    """
    Authenticates a WebSocket connection request for a single-user service.
    Enhanced with device ID validation.

    Args:
        request: The incoming aiohttp request object.
        session_manager: The session manager instance.

    Returns:
        A tuple containing: (user_id, session_id, device_id)

    Raises:
        ClientError: If required parameters are missing.
        WebSocketError: If the token is invalid.
    """
    # Existing code for logging and parameter extraction
    logger.info(f"Authenticating WebSocket request from {request.remote}")
    logger.info(f"Request query parameters: {dict(request.query)}")

    query = request.query
    token = query.get('token')
    device_id = query.get('deviceId')

    # Log parameter presence
    logger.info(f"Auth parameters - token present: {token is not None}, deviceId present: {device_id is not None}")

    # Validate required parameters
    if not token:
        logger.warning("Authentication failed: Missing token query parameter")
        raise ClientError(
            message="Missing required parameter: token",
            error_code="MISSING_PARAMETERS"
        )

    if not device_id:
        logger.warning("Authentication failed: Missing deviceId query parameter")
        raise ClientError(
            message="Missing required parameter: deviceId",
            error_code="MISSING_PARAMETERS"
        )

    # Get the session ID (in single-user mode, it's pre-defined)
    session_id = session_manager.state_manager.get_active_session_id()

    # Validate token
    validation_result = await validate_token_with_auth_service(token)

    if not validation_result.get('valid', False):
        logger.warning(f"Authentication failed: Invalid token for device {device_id}")
        raise WebSocketError(
            message="Invalid authentication token",
            error_code="AUTH_FAILED"
        )

    user_id = validation_result.get('userId')

    if not user_id:
        logger.warning(f"Authentication failed: No user ID in token for device {device_id}")
        raise WebSocketError(
            message="Invalid authentication token - missing user ID",
            error_code="AUTH_FAILED"
        )

    # Rest of the function remains unchanged...
    # Check if device ID matches existing session
    session = await session_manager.get_session()

    if not session:
        logger.warning(f"Session not found during WebSocket authentication, continue with new session.")
        return user_id, device_id

    details = session.details if session else None
    existing_device_id = details.device_id if details else None

    # CHANGE: Instead of rejecting the new device, flag it for replacement
    if existing_device_id and existing_device_id != device_id:
        logger.warning(f"Device mismatch: User {user_id} attempting connection with device {device_id}, "
                       f"but session is active on device {existing_device_id}")

        # Instead of raising an exception, store the current (old) device ID so we can handle it later
        # This will allow the new device but signal WebSocketManager to handle the transition
        request['previous_device_id'] = existing_device_id
        logger.info(f"Allowing new device {device_id} to replace existing device {existing_device_id}")

    logger.info(f"WebSocket authenticated for user {user_id}, device {device_id}, session {session_id}")

    # Update the session details with the device ID and connection timestamp
    await session_manager.store_manager.session_store.update_session_details(session_id, {
        'device_id': device_id,
        'last_connection': time.time(),
        'user_agent': request.headers.get('User-Agent', 'unknown'),
        'ip_address': request.remote
    })

    return user_id, device_id


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
