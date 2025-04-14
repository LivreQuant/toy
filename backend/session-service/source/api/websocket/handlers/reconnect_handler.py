# websocket/handlers/reconnect_handler.py
"""
Handler for the 'reconnect' WebSocket message type.
Simplified for singleton session mode.
"""
import logging
import time
from typing import Dict, Any, TYPE_CHECKING

from opentelemetry import trace
from aiohttp import web

from source.core.state.manager import StateManager
from source.core.session.manager import SessionManager
from source.utils.metrics import track_websocket_message
from source.utils.tracing import optional_trace_span

logger = logging.getLogger('websocket_handler_reconnect')


async def handle_reconnect(
        *,
        ws: web.WebSocketResponse,
        user_id: str,
        client_id: str,
        device_id: str,
        message: Dict[str, Any],
        session_manager: SessionManager,
        tracer: trace.Tracer,
        **kwargs  # Accept additional parameters for compatibility
):
    """
    Process a reconnect message from the client.
    In singleton mode, this always succeeds.

    Args:
        ws: The WebSocket connection.
        user_id: User ID (from initial connection auth).
        client_id: Client ID.
        message: The parsed reconnect message dictionary.
        session_manager: Direct access to SessionManager.
        tracer: OpenTelemetry Tracer instance.
    """
    with optional_trace_span(tracer, "handle_reconnect_message") as span:
        span.set_attribute("client_id", client_id)

        # Extract data from message
        device_id = message.get('deviceId')
        request_id = message.get('requestId', f'reconnect-{time.time_ns()}')  # Generate if missing

        span.set_attribute("device_id_from_client", str(device_id))
        span.set_attribute("request_id", request_id)
        
        # In singleton mode, prepare successful response
        success = True
        response_message = "Session reconnected successfully"
        
        # Get session metadata
        session_metadata = await session_manager.get_session_metadata()
        simulator_status = session_metadata.get('simulator_status', 'NONE') if session_metadata else 'NONE'
        
        # Update connection count in session metadata
        try:
            # Try to update metadata with device ID if provided
            if device_id:
                session_id = session_manager.state_manager.get_active_session_id()
                await session_manager.update_session_metadata({
                    'device_id': device_id,
                    'last_reconnect': time.time()
                })
        except Exception as e:
            logger.error(f"Failed to update metadata during reconnect: {e}")

        response = {
            'type': 'reconnect_result',
            'requestId': request_id,
            'success': success,
            'message': response_message,
            'deviceId': device_id,
            'deviceIdValid': True,  # Always valid in singleton mode
            'sessionStatus': 'valid',  # Always valid in singleton mode
            'simulatorStatus': simulator_status
        }

        try:
            if not ws.closed:
                await ws.send_json(response)
                track_websocket_message("sent", "reconnect_result_success")
        except Exception as e:
            logger.error(f"Failed to send reconnect_result for client {client_id}: {e}")
            