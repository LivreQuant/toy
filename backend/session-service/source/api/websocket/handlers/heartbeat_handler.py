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

from source.api.websocket.emitters.connection_emitter import send_device_id_invalidated
from source.core.session.manager import SessionManager
from source.utils.metrics import track_websocket_message
from source.utils.tracing import optional_trace_span
from source.models.session import SessionStatus

logger = logging.getLogger('websocket_handler_heartbeat')


async def handle_heartbeat(
        *,
        ws: web.WebSocketResponse,
        user_id: str,
        client_id: str,
        device_id: str,
        message: Dict[str, Any],
        session_manager: SessionManager,
        tracer: trace.Tracer,
        **kwargs
):
    """Process a heartbeat message from the client."""
    with optional_trace_span(tracer, "handle_heartbeat_message") as span:
        span.set_attribute("client_id", client_id)

        # Extract data from message
        client_timestamp = message.get('timestamp', int(time.time() * 1000))
        device_id_from_message = message.get('deviceId', device_id)
        connection_quality = message.get('connectionQuality', 'unknown')

        # Get session data to check if session is active and if device ID matches
        session = await session_manager.get_session()

        if not session:
            logger.warning(f"Session not found for heartbeat from device {device_id}")
            await send_device_id_invalidated(
                ws,
                device_id=device_id,
                reason="Session not found"
            )
            # Reset session state BUT don't stop simulators
            await session_manager.state_manager.close(keep_simulator=True)
            return

        # Check if the session is still active
        if session.status != SessionStatus.ACTIVE:
            logger.info(f"Session {session.session_id} is no longer active (status: {session.status.value})")
            await send_device_id_invalidated(
                ws,
                device_id=device_id,
                reason="Another device has connected with this account"
            )

            # Reset session state BUT don't stop simulators
            await session_manager.state_manager.close(keep_simulator=True)
            return

        # Get session details
        session_details = await session_manager.get_session_details()

        # Check if this device ID is still the active one for this session
        active_device_id = session_details.get('device_id') if session_details else None

        if active_device_id and active_device_id != device_id:
            logger.info(f"Device {device_id} is no longer active. Active device is {active_device_id}")
            # Send invalidation message
            await send_device_id_invalidated(
                ws,
                device_id=active_device_id,
                reason="Another device has connected with this account"
            )

            # Reset session state BUT don't stop simulators
            await session_manager.state_manager.close(keep_simulator=True)
            return

        # Device is still active - update session activity timestamp
        await session_manager.update_session_activity()

        # Get simulator status from database
        simulator_status_server = session_details.get('simulator_status', 'NONE') if session_details else 'NONE'

        # Prepare response
        response = {
            'type': 'heartbeat_ack',
            'timestamp': int(time.time() * 1000),
            'clientTimestamp': client_timestamp,
            'deviceId': device_id,
            'deviceIdValid': True,
            'sessionStatus': 'valid',
            'simulatorStatus': simulator_status_server,
            'connectionQualityUpdate': connection_quality,
        }

        try:
            if not ws.closed:
                await ws.send_json(response)
                track_websocket_message("sent", "heartbeat_ack")
        except Exception as e:
            logger.error(f"Failed to send heartbeat_ack for client {client_id}: {e}")
