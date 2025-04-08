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
    from source.core.session_manager import SessionManager

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

        # Validate device ID against session metadata
        device_id_valid = False
        current_device_id = None
        simulator_status_server = 'none' # Default
        session_valid_server = False

        # Get session from database - this returns a Session object, not a dictionary
        session = await session_manager.get_session(session_id)
        
        if session:
            logger.info(f"Heartbeat handling - Session object type: {type(session)}")
            logger.info(f"Heartbeat handling - Session attributes: {dir(session)}")
            if hasattr(session, 'metadata'):
                logger.info(f"Heartbeat handling - Metadata type: {type(session.metadata)}")
                logger.info(f"Heartbeat handling - Metadata attributes: {dir(session.metadata)}")
                if hasattr(session.metadata, 'device_id'):
                    logger.info(f"Heartbeat handling - Found device_id in metadata: {session.metadata.device_id}")
                else:
                    logger.warning(f"Heartbeat handling - No device_id attribute in metadata")
            else:
                logger.warning(f"Heartbeat handling - No metadata attribute in session")
                
            session_valid_server = True # Assume valid if found
            
            # Access metadata as an attribute of the Session object
            # Session should have a metadata attribute which is a SessionMetadata object
            metadata = session.metadata if hasattr(session, 'metadata') else None
            logger.debug(f"Session metadata for {session_id}: {metadata}")
            
            if metadata:
                # Access device_id as an attribute of the SessionMetadata object
                current_device_id = metadata.device_id if hasattr(metadata, 'device_id') else None
                logger.debug(f"Extracted device_id from metadata: {current_device_id}")
                
                # Access simulator_status as an attribute
                # Convert to string if it's an enum
                if hasattr(metadata, 'simulator_status'):
                    simulator_status_server = metadata.simulator_status
                    # If it's an enum, get its value
                    if hasattr(simulator_status_server, 'value'):
                        simulator_status_server = simulator_status_server.value
                
                # Compare device IDs as strings to handle type differences
                if current_device_id and str(device_id) == str(current_device_id):
                    device_id_valid = True
                else:
                    logger.warning(f"Heartbeat for session {session_id} had mismatched device ID. Client sent: '{device_id}', Server expects: '{current_device_id}'")
                    span.set_attribute("error", "Device ID mismatch")
            else:
                logger.warning(f"Session {session_id} has no metadata")
                span.set_attribute("error", "Session missing metadata")
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
                logger.debug(f"Sent heartbeat_ack to client {client_id} with deviceIdValid={device_id_valid}, sessionStatus={response['sessionStatus']}")
        except Exception as e:
            logger.error(f"Failed to send heartbeat_ack for session {session_id}, client {client_id}: {e}")
            # Don't re-raise, let the connection manage itself