# websocket/handlers/reconnect_handler.py
"""
Handler for the 'reconnect' WebSocket message type.
"""
import logging
import time
from typing import Dict, Any, TYPE_CHECKING

from opentelemetry import trace
from aiohttp import web

from source.core.session.manager import SessionManager
from source.utils.metrics import track_websocket_message
from source.utils.tracing import optional_trace_span

if TYPE_CHECKING:
    from source.api.websocket.registry import WebSocketRegistry

logger = logging.getLogger('websocket_handler_reconnect')


async def handle_reconnect(
        *,
        ws: web.WebSocketResponse,
        session_id: str,
        user_id: str,
        client_id: str,
        message: Dict[str, Any],
        session_manager: SessionManager,
        registry: 'WebSocketRegistry',
        tracer: trace.Tracer
):
    """
    Process a reconnect message from the client.
    This typically re-validates the session and device using provided tokens.

    Args:
        ws: The WebSocket connection.
        session_id: Session ID (from the initial connection params or message).
        user_id: User ID (from initial connection auth).
        client_id: Client ID.
        message: The parsed reconnect message dictionary.
        session_manager: Direct access to SessionManager.
        registry: Direct access to WebSocketRegistry.
        tracer: OpenTelemetry Tracer instance.
    """
    with optional_trace_span(tracer, "handle_reconnect_message") as span:
        span.set_attribute("session_id", session_id)
        span.set_attribute("client_id", client_id)

        # Extract data from message
        device_id = message.get('deviceId')
        session_token = message.get('sessionToken')  # Assuming token comes in message body
        request_id = message.get('requestId', f'reconnect-{time.time_ns()}')  # Generate if missing

        span.set_attribute("device_id_from_client", str(device_id))
        span.set_attribute("request_id", request_id)

        success = False
        response_message = "Reconnect failed"
        device_id_valid_server = False
        session_status_server = 'invalid'
        simulator_status_server = 'none'
        authoritative_device_id = None  # The device ID confirmed by the server

        if not device_id or not session_token:
            response_message = "Missing deviceId or sessionToken in reconnect request"
            span.set_attribute("error", response_message)
        else:
            # Validate the session directly through the session manager
            validated_user_id = await session_manager.validate_session(session_id, user_id, session_token, device_id)

            if validated_user_id:
                # Session validation successful, get session details
                span.set_attribute("validated_user_id", str(validated_user_id))

                # Get session metadata using session manager
                session_metadata = await session_manager.get_session_metadata(session_id)

                if session_metadata:
                    success = True
                    device_id_valid_server = True  # Validation passed
                    session_status_server = 'valid'
                    response_message = "Session reconnected successfully"
                    authoritative_device_id = device_id  # Use the validated device ID
                    simulator_status_server = session_metadata.get('simulator_status', 'none')

                    # Update connection activity directly in registry
                    registry.update_connection_activity(ws)
                else:
                    # Should not happen if validate_session passed, but handle defensively
                    response_message = "Reconnect validation passed but session data not found"
                    span.set_attribute("error", response_message)
                    success = False  # Mark as failed if session data is missing
            else:
                response_message = "Invalid session, token, or device ID provided for reconnect"
                span.set_attribute("error", response_message)

                # Check if session exists but device ID is wrong
                session = await session_manager.get_session(session_id)
                if session:
                    session_metadata = await session_manager.get_session_metadata(session_id)
                    if session_metadata:
                        authoritative_device_id = session_metadata.get('device_id')
                        if authoritative_device_id != device_id:
                            device_id_valid_server = False  # Device ID was the issue
                            session_status_server = 'valid'  # Session exists, device is wrong

        response = {
            'type': 'reconnect_result',
            'requestId': request_id,
            'success': success,
            'message': response_message,
            'deviceId': authoritative_device_id,  # Send the server's known/validated device ID
            'deviceIdValid': device_id_valid_server,
            'sessionStatus': session_status_server,
            'simulatorStatus': simulator_status_server
        }

        metric_label = "reconnect_result_success" if success else "reconnect_result_failure"
        try:
            if not ws.closed:
                await ws.send_json(response)
                track_websocket_message("sent", metric_label)
        except Exception as e:
            logger.error(f"Failed to send reconnect_result for session {session_id}, client {client_id}: {e}")
