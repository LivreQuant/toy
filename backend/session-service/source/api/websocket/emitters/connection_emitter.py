# websocket/emitters/connection_emitter.py
"""
Handles sending connection lifecycle related messages to clients.
(connected, timeout, shutdown)
"""
import logging
import time
from typing import Dict, Any
from aiohttp import web

from source.utils.metrics import track_websocket_message
from source.config import config

logger = logging.getLogger('websocket_emitter_connection')


async def send_connected(
        ws: web.WebSocketResponse,
        *,
        client_id: str,
        device_id: str,
        pod_name: str = None  # Allow injection for testing
):
    """Sends the 'connected' message upon successful registration."""
    if pod_name is None:
        pod_name = config.kubernetes.pod_name

    payload = {
        'type': 'connected',
        'clientId': client_id,
        'deviceId': device_id,
        'podName': pod_name,
        'timestamp': int(time.time() * 1000)
    }
    try:
        if not ws.closed:
            await ws.send_json(payload)
            track_websocket_message("sent", "connected")
            logger.debug(f"Sent 'connected' to client {client_id} in session")
        else:
            logger.warning(f"Attempted to send 'connected' to already closed WS for client {client_id}")
    except Exception as e:
        logger.error(f"Failed to send 'connected' message to client {client_id}: {e}")


async def send_timeout(ws: web.WebSocketResponse):
    """Sends the 'timeout' message before closing a stale connection."""
    payload = {
        'type': 'timeout',
        'message': 'Connection timed out due to inactivity',
        'timestamp': int(time.time() * 1000)
    }
    try:
        if not ws.closed:
            await ws.send_json(payload)
            track_websocket_message("sent", "timeout")
            logger.debug(f"Sent 'timeout'")  # Use address if client_id unknown here
    except Exception as e:
        # Log error, but likely the connection is already broken
        logger.warning(f"Failed to send 'timeout' message: {e}")


async def send_shutdown(ws: web.WebSocketResponse, reason: str):
    """Sends the 'shutdown' message when the server is stopping."""
    payload = {
        'type': 'shutdown',
        'message': reason,
        'timestamp': int(time.time() * 1000)
    }
    try:
        if not ws.closed:
            await ws.send_json(payload)
            track_websocket_message("sent", "shutdown")
            logger.debug(f"Sent 'shutdown'")
    except Exception as e:
        logger.warning(f"Failed to send 'shutdown' message: {e}")
