# websocket/handlers/heartbeat_handler.py
"""
Handler for the 'heartbeat' WebSocket message type.
"""
import logging
import time
from typing import Dict, Any, TYPE_CHECKING

from opentelemetry import trace
from aiohttp import web

# Assuming these utilities exist and are correctly path-imported
from source.utils.metrics import track_websocket_message
from source.utils.tracing import optional_trace_span

# Type hints for managers without circular import
if TYPE_CHECKING:
    from ..manager import WebSocketManager
    from source.core.session_manager import SessionManager # Adjust import path

logger = logging.getLogger('websocket_handler_heartbeat')


async def handle_heartbeat(
    *, # Make arguments keyword-only for clarity
    ws: web.WebSocketResponse,
    session_id: str,
    user_id: Any, # Keep original type flexible if needed
    client_id: str,
    message: Dict[str, Any],
    session_manager: 'SessionManager',
    ws_manager: 'WebSocketManager',
    tracer: trace.Tracer
):
    """
    Process a heartbeat message from the client.

    Args:
        ws: The WebSocket connection.
        session_id: Session ID.
        user_id: User ID.
        client_id: Client ID.
        message: The parsed heartbeat message dictionary.
        session_manager: Instance of the SessionManager.
        ws_manager: Instance of the WebSocketManager.
        tracer: OpenTelemetry Tracer instance.
    """
    with optional_trace_span(tracer, "handle_heartbeat_message") as span:
        span.set_attribute("session_id", session_id)
        span.set_attribute("client_id", client_id)

        # Extract data from message (provide defaults or handle missing keys)
        client_timestamp = message.get('timestamp', int(time.time() * 1000)) # Use client time if possible
        device_id = message.get('deviceId')
        # Optional fields from original code - retain if needed
        connection_quality = message.get('connectionQuality', 'unknown')
        session_status_client = message.get('sessionStatus', 'unknown')
        simulator_status_client = message.get('simulatorStatus', 'unknown')

        span.set_attribute("client_timestamp", client_timestamp)
        span.set_attribute("device_id_from_client", str(device_id))
        span.set_attribute("connection_quality_client", connection_quality)
        span.set_attribute("session_status_client", session_status_client)
        span.set_attribute("simulator_status_client", simulator_status_client)


        # Update last activity time in connection info stored in manager
        # This is now done more generically in the manager's message loop
        # if ws in ws_manager.connection_info:
        #    ws_manager.connection_info[ws]['last_activity'] = time.time()
        # else:
        #    logger.warning(f"Heartbeat received for untracked websocket? Session {session_id}, Client {client_id}")


        # Validate device ID against session metadata
        device_id_valid = False
        current_device_id = None
        simulator_status_server = 'none' # Default
        session_valid_server = False

        session = await session_manager.get_session(session_id)
        if session:
            session_valid_server = True # Assume valid if found
            metadata = session.get('metadata') # Assuming metadata is an object or dict
            if metadata:
                 # Use getattr for safer access if metadata is an object, or .get if dict
                 current_device_id = getattr(metadata, 'device_id', None) or metadata.get('device_id')
                 simulator_status_server = getattr(metadata, 'simulator_status', 'none') or metadata.get('simulator_status', 'none')

            if current_device_id and device_id == current_device_id:
                device_id_valid = True
            else:
                logger.warning(f"Heartbeat for session {session_id} had mismatched device ID. Client sent: '{device_id}', Server expects: '{current_device_id}'")
                span.set_attribute("error", "Device ID mismatch")
        else:
            logger.warning(f"Heartbeat received for non-existent session: {session_id}")
            span.set_attribute("error", "Session not found")
            session_valid_server = False # Explicitly mark session as invalid server-side


        # Prepare response
        response = {
            'type': 'heartbeat_ack',
            'timestamp': int(time.time() * 1000),
            'clientTimestamp': client_timestamp, # Echo client timestamp
            'deviceId': current_device_id,       # Send the authoritative device ID
            'deviceIdValid': device_id_valid,
            'sessionStatus': 'valid' if session_valid_server and device_id_valid else 'invalid',
            'simulatorStatus': simulator_status_server, # Report current server-side status
            # Include connectionQualityUpdate if client expects it back
            'connectionQualityUpdate': connection_quality,
        }

        try:
            if not ws.closed:
                await ws.send_json(response)
                track_websocket_message("sent", "heartbeat_ack")
        except Exception as e:
             logger.error(f"Failed to send heartbeat_ack for session {session_id}, client {client_id}: {e}")
             # Don't re-raise, let the connection manage itself

        # Optionally, instruct manager to close connection if device ID is invalid
        # This logic was implicit before, make it explicit if desired
        # if not device_id_valid:
        #     logger.info(f"Closing connection due to invalid device ID in heartbeat: session={session_id}, client={client_id}")
        #     try:
        #         await ws.close(code=4003, message=b'Invalid device for session')
        #     except: pass # Ignore errors on close
        #     # Unregistration will happen in the main manager loop's finally block