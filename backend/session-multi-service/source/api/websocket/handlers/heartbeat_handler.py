# websocket/handlers/heartbeat_handler.py
"""
Handler for the 'heartbeat' WebSocket message type.
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
        tracer: trace.Tracer
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
        span.set_attribute("session_status_client", session_status_client)
        span.set_attribute("simulator_status_client", simulator_status_client)

        # Get session and validate device ID
        device_id_valid_server = False
        current_device_id = None
        simulator_status_server = 'none'  # Default

        # Get session from database through the session manager directly
        session = await session_manager.get_session(session_id)

        if session:
            session_valid_server = True  # Session exists

            # Get device ID and simulator status through session manager's methods
            session_metadata = await session_manager.get_session_metadata(session_id)

            if session_metadata:
                current_device_id = session_metadata.get('device_id')
                simulator_status_server = session_metadata.get('simulator_status', 'none')

                # Compare device IDs as strings to handle type differences
                if current_device_id and str(device_id) == str(current_device_id):
                    device_id_valid_server = True
                else:
                    logger.warning(
                        f"Heartbeat for session {session_id} had mismatched device ID. "
                        f"Client sent: '{device_id}', Server expects: '{current_device_id}'"
                    )
                    span.set_attribute("error", "Device ID mismatch")
            else:
                logger.warning(f"Session {session_id} has no metadata")
                span.set_attribute("error", "Session missing metadata")
        else:
            logger.warning(f"Heartbeat received for non-existent session: {session_id}")
            span.set_attribute("error", "Session not found")
            session_valid_server = False  # Explicitly mark session as invalid server-side

        # Prepare response
        response = {
            'type': 'heartbeat_ack',
            'timestamp': int(time.time() * 1000),
            'clientTimestamp': client_timestamp,  # Echo client timestamp
            'deviceId': current_device_id,  # Send the authoritative device ID
            'deviceIdValid': device_id_valid_server,
            'sessionStatus': 'valid' if session_valid_server and device_id_valid_server else 'invalid',
            'simulatorStatus': simulator_status_server,  # Report current server-side status
            # Include connectionQualityUpdate if client expects it back
            'connectionQualityUpdate': connection_quality,
        }

        try:
            if not ws.closed:
                await ws.send_json(response)
                track_websocket_message("sent", "heartbeat_ack")
                logger.debug(
                    f"Sent heartbeat_ack to client {client_id} with "
                    f"deviceIdValid={device_id_valid_server}, sessionStatus={response['sessionStatus']}"
                )
        except Exception as e:
            logger.error(f"Failed to send heartbeat_ack for session {session_id}, client {client_id}: {e}")
