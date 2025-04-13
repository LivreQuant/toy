# source/authentication.py
import logging
from typing import Tuple

from aiohttp import web
from source.api.utils import validate_token_with_auth_service

logger = logging.getLogger('authentication')


async def authenticate_websocket(request: web.Request) -> Tuple[str, str]:
    """
    Authenticate WebSocket connection

    Args:
        request: WebSocket connection request

    Returns:
        Tuple of (user_id, device_id)
    """
    query = request.query
    token = query.get('token')
    device_id = query.get('deviceId', 'default-device')

    if not token:
        raise ValueError("Missing authentication token")

    # Validate token
    validation_result = await validate_token_with_auth_service(token)

    if not validation_result.get('valid', False):
        raise ValueError("Invalid authentication token")

    user_id = validation_result.get('userId')

    if not user_id:
        raise ValueError("No user ID found in token")

    return user_id, device_id
