# websocket/authenticator.py
"""
Handles authentication and session validation/creation for incoming WebSocket requests.
"""
import logging
import time
from typing import Tuple, Any, TYPE_CHECKING

from aiohttp import web

# Assuming SessionManager type hint is available
if TYPE_CHECKING:
    from source.core.session.session_manager import SessionManager

# Import custom exceptions
from .exceptions import (
    WebSocketClientError,
    AuthenticationError,
    WebSocketServerError
)

logger = logging.getLogger('websocket_authenticator')

async def authenticate_websocket_request(
    request: web.Request,
    session_manager: 'SessionManager'
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
        Exception: For other unexpected errors during the process.
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

    # 2. Validate Session / Token and Get User ID
    try:
        if session_id:
            # Attempt to validate existing session
            logger.debug(f"Validating existing session {session_id} for device {device_id}")

            logger.info(f"authenticator - authenticate_websocket_request - session validation: {session_id}")

            user_id = await session_manager.validate_session(session_id, token, device_id)
            if not user_id:
                # Session is invalid/expired, or device doesn't match.
                # Fallback: Check if token itself is valid for potential new session.
                logger.warning(f"Session {session_id} validation failed. Checking token validity for potential new session.")
                user_id = await session_manager.get_user_from_token(token)
                session_id = None # Mark session as invalid/non-existent for creation step
            else:
                 logger.debug(f"Session {session_id} validated successfully for user {user_id}")

        else:
            # No session ID provided, validate token directly to get user
            logger.debug(f"No session ID provided, validating token for device {device_id}")
            user_id = await session_manager.get_user_from_token(token)

        # If no valid user could be determined from session or token
        if not user_id:
            logger.warning(f"Authentication failed: Invalid token provided for device {device_id}")
            raise AuthenticationError(
                message="Invalid authentication token",
                error_code="INVALID_TOKEN"
            )

        # 3. Check for recent sessions before creating a new one
        if not session_id:
            # Before creating a new session, check for very recent sessions
            recent_sessions = await session_manager.db_manager.get_active_user_sessions(user_id)
            # Sort by creation time, newest first
            recent_sessions.sort(key=lambda s: s.created_at, reverse=True)

            # If there's a very recent session (within last 5 seconds), use it instead of creating a new one
            current_time = time.time()
            for session in recent_sessions:
                # Check if session was created in the last 5 seconds
                if current_time - session.created_at < 5:
                    logger.info(f"Using recently created session {session.session_id} instead of creating a new one")
                    session_id = session.session_id
                    # Make sure device ID is consistent
                    if hasattr(session.metadata, 'device_id') and session.metadata.device_id != device_id:
                        await session_manager.db_manager.update_session_metadata(session_id, {'device_id': device_id})
                    return user_id, session_id, device_id

            # If no recent session found, create a new one
            client_ip = request.remote
            logger.info(f"No valid session found for user {user_id}, device {device_id}. Creating new session from IP {client_ip}.")
            session_id, is_new = await session_manager.create_session(user_id, device_id, token, client_ip)

            if not session_id:
                # This indicates an internal problem with session creation
                logger.error(f"Failed to create session for user {user_id}, device {device_id}")
                raise WebSocketServerError(
                    message="Failed to create session",
                    error_code="SESSION_CREATION_FAILED"
                )
            logger.info(f"Successfully created new session {session_id} for user {user_id}, device {device_id}")

        # 4. Success: Return validated/created details
        logger.info(f"WebSocket authentication successful: user={user_id}, session={session_id}, device={device_id}")
        return user_id, session_id, device_id

    except (WebSocketClientError, AuthenticationError, WebSocketServerError):
         # Re-raise known errors to be handled by the caller
         raise
    except Exception as e:
        # Catch any other unexpected errors during the process
        logger.error(f"Unexpected error during WebSocket authentication for device {device_id}: {e}", exc_info=True)
        # Wrap in a generic server error - avoid raising raw Exception