# websocket/emitters/session_emitter.py
"""
Handles sending session status updates to clients.
"""
import logging
import time
from typing import Optional

from aiohttp import web

from source.utils.metrics import track_websocket_message

logger = logging.getLogger('websocket_emitter_session')


async def send_simulator_status_update(
        ws: web.WebSocketResponse,
        *,
        simulator_id: Optional[str],
        status: str,
        client_id: Optional[str] = None,
):
    """Sends the 'simulator_status_update' message when simulator status changes."""
    payload = {
        'type': 'simulator_status_update',
        'simulatorId': simulator_id,
        'simulatorStatus': status,
        'timestamp': int(time.time() * 1000)
    }

    try:
        if not ws.closed:
            await ws.send_json(payload)
            track_websocket_message("sent", "simulator_status_update")
            logger.info(f"Sent 'simulator_status_update' with status {status} to client {client_id}")
        else:
            logger.warning(f"Attempted to send 'simulator_status_update' to already closed WS")
    except Exception as e:
        logger.error(f"Failed to send 'simulator_status_update' message: {e}")