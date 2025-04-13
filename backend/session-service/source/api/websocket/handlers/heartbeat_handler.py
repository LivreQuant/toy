# websocket/handlers/heartbeat_handler.py
"""
Handler for the 'heartbeat' WebSocket message type.
Simplified for singleton session mode.
"""
import logging
import time
from typing import Dict, Any

from opentelemetry import trace
from aiohttp import web

from source.core.session.manager import SessionManager
from source.utils.metrics import track_websocket_message
from source.utils.tracing import optional_trace_span

logger = logging.getLogger('websocket_handler_heartbeat')


async def handle_heartbeat(
        *,
        ws: web.WebSocketResponse,
        session_id: str,
        client_id: str,
        message: Dict[str, Any],
        session_manager: SessionManager,
        tracer: trace.Tracer,
        **kwargs  # Accept additional parameters for compatibility
):
    """
    Process a heartbeat message from the client.

    Args:
        ws: The WebSocket connection.
        session_id: Session ID.
        client_id: Client ID.
        message: The parsed heartbeat message dictionary.
        session_manager: Direct access to SessionManager.
        tracer: OpenTelemetry Tracer instance.
    """
    with optional_trace_span(tracer, "handle_heartbeat_message") as span:
        span.set_attribute("session_id", session_id)
        span.set_attribute("client_id", client_id)

        # Extract data from message (provide defaults or handle missing keys)
        client_timestamp = message.get('timestamp', int(time.time() * 1000))
        device_id = message.get('deviceId')
        # Optional fields
        connection_quality = message.get('connectionQuality', 'unknown')
        session_status_client = message.get('sessionStatus', 'unknown')
        simulator_status_client = message.get('simulatorStatus', 'unknown')

        span.set_attribute("client_timestamp", client_timestamp)
        span.set_attribute("device_id_from_client", str(device_id))
        span.set_attribute("connection_quality_client", connection_quality)
        
        # Update session activity timestamp
        await session_manager.update_session_activity(session_id)

        # Get latest session data
        session_metadata = await session_manager.get_session_metadata(session_id)
        simulator_status_server = session_metadata.get('simulator_status', 'NONE') if session_metadata else 'NONE'
        current_device_id = session_metadata.get('device_id') if session_metadata else None

        # Prepare response - in singleton mode, session is always valid
        response = {
            'type': 'heartbeat_ack',
            'timestamp': int(time.time() * 1000),
            'clientTimestamp': client_timestamp,
            'deviceId': current_device_id,
            'deviceIdValid': True,  # Always valid in singleton mode
            'sessionStatus': 'valid',  # Always valid in singleton mode
            'simulatorStatus': simulator_status_server,
            'connectionQualityUpdate': connection_quality,
        }

        try:
            if not ws.closed:
                await ws.send_json(response)
                track_websocket_message("sent", "heartbeat_ack")
        except Exception as e:
            logger.error(f"Failed to send heartbeat_ack for client {client_id}: {e}")
            