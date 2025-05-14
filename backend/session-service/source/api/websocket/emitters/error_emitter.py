# websocket/emitters/error_emitter.py
"""
Simplified error message emitter for WebSocket clients.
"""
import logging
from typing import Optional

from aiohttp import web
from source.utils.metrics import track_websocket_error

logger = logging.getLogger('websocket_emitter_error')


async def send_error(
        ws: web.WebSocketResponse,
        *,
        error_code: str,
        message: str,
        request_id: Optional[str] = None,
        span = None  # Add default None parameter
):
    """
    Sends a standardized error payload to the client.

    Args:
        ws: The WebSocket connection.
        error_code: Machine-readable error code.
        message: Human-readable error description.
        request_id: Optional client request ID to echo back.
    """
    error_payload = {
        'type': 'error',
        'errorCode': error_code,
        'message': message,
    }
    if request_id:
        error_payload['requestId'] = request_id

    # Track the error metric
    track_websocket_error(error_code)

    # Attempt to send the error payload to the client
    try:
        if not ws.closed:
            await ws.send_json(error_payload)
        else:
            logger.warning(f"Cannot send error '{error_code}', WebSocket connection already closed.")
    except Exception as send_error:
        logger.error(f"Failed to send error payload ({error_code}) back to client: {send_error}")
