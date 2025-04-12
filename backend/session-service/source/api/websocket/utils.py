# source/api/websocket/authenticator.py
"""
Handles authentication and session validation/creation for incoming WebSocket requests.
"""
import logging
from typing import Tuple, Any

from aiohttp import web

from source.api.utils import validate_token_with_auth_service
from source.api.websocket.exceptions import (
    WebSocketClientError,
    AuthenticationError,
    WebSocketServerError
)

logger = logging.getLogger('websocket_authenticator')


async def authenticate_websocket_request(
        request: web.Request,
        session_manager
) -> Tuple[Any, str, str]:
    """
    Authenticates a WebSocket connection request and establishes session details.

    Args:
        request: The incoming aiohttp request object.
        session_manager: The session manager instance.

    Returns:
        A tuple containing: (user_id, session_id, device_id)

    Raises:
        WebSocketClientError: If required parameters are missing or invalid input.
        AuthenticationError: If the token or session is invalid.
        WebSocketServerError: If session creation fails unexpectedly.
    """
    query = request.query
    token = query.get('token')
    device_id = query.get('deviceId')
    session_id_from_query = query.get('sessionId')

    # 1. Validate required parameters
    if not token or not device_id:
        logger.warning("Authentication failed: Missing token or deviceId query parameter.")
        raise WebSocketClientError(
            message="Missing required parameters: token or deviceId",
            error_code="MISSING_PARAMETERS"
        )

    logger.debug(f"Attempting WebSocket authentication for device: {device_id}, session_query: {session_id_from_query}")

    user_id = None
    # Use session_id from query if provided, otherwise it's None and needs creation
    session_id = session_id_from_query

    # 2. Validate Token Directly with Auth Service
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

    # 3. If session_id provided, validate it belongs to this user
    if session_id:
        session = await session_manager.get_session(session_id)
        if not session or session.user_id != user_id:
            logger.warning(f"Session {session_id} validation failed for user {user_id}")
            session_id = None  # Mark for new session creation
        elif hasattr(session.metadata, 'device_id') and session.metadata.device_id != device_id:
            # Device ID mismatch - decide how to handle (continue with new session in this case)
            logger.warning(
                f"Device ID mismatch for session {session_id}. Expected {session.metadata.device_id}, got {device_id}")
            session_id = None  # Mark for new session creation

    # 4. Create new session if needed
    if not session_id:
        client_ip = request.remote
        logger.info(f"Creating new session for user {user_id}, device {device_id} from IP {client_ip}")
        session_id, is_new = await session_manager.create_session(user_id, device_id, token, client_ip)

        if not session_id:
            # This indicates an internal problem with session creation
            logger.error(f"Failed to create session for user {user_id}, device {device_id}")
            raise WebSocketServerError(
                message="Failed to create session",
                error_code="SESSION_CREATION_FAILED"
            )
        logger.info(f"Successfully created new session {session_id} for user {user_id}, device {device_id}")

    return user_id, session_id, device_id
