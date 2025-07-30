# backend/session-service/source/api/websocket/handlers/heartbeat_handler.py
"""
Handler for the 'heartbeat' WebSocket message type.
Now uses gRPC status from background simulator manager.
"""
import logging
import time
from typing import Dict, Any

from opentelemetry import trace
from aiohttp import web

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

        # Session is valid
        device_id_valid = True
        reason = ""

        # Get session data to check if session is active and if device ID matches
        session = await session_manager.get_session()

        if not session:
            logger.warning(f"Session not found for heartbeat from device {device_id}")

            device_id_valid = False
            reason = "Session not found"

            # Prepare response
            response = {
                'type': 'heartbeat_ack',
                'timestamp': int(time.time() * 1000),
                'clientTimestamp': client_timestamp,
                'deviceId': device_id,
                'deviceIdValid': device_id_valid,
                'reason': reason,
                'simulatorStatus': "NONE",
            }

            try:
                if not ws.closed:
                    await ws.send_json(response)
                    track_websocket_message("sent", "heartbeat_ack")

            except Exception as e:
                logger.error(f"Failed to send heartbeat_ack for client {client_id}: {e}")

            if not device_id_valid:
                await session_manager.state_manager.close(keep_simulator=True)

            return

        # Check if the session is still active
        if session.status != SessionStatus.ACTIVE:
            logger.info(f"Session {session.session_id} is no longer active (status: {session.status.value})")

            device_id_valid = False
            reason = "Another device has connected with this account"

        # Get session details
        session_details = await session_manager.get_session_details()

        # Check if this device ID is still the active one for this session
        active_device_id = session_details.get('device_id') if session_details else None

        if active_device_id and active_device_id != device_id:
            logger.info(f"Device {device_id} is no longer active. Active device is {active_device_id}")
            # Send invalidation message

            device_id_valid = False
            reason = "Another device has connected with this account"

        # Device is still active - update session activity timestamp
        await session_manager.update_session_activity()

        # Get simulator status from background simulator manager (REAL-TIME via gRPC)
        simulator_status_server = "NONE"
        session_id = session_manager.state_manager.get_active_session_id()
        
        if session_manager.background_simulator_manager:
            # Get real-time status from background simulator manager
            simulator_status_server = session_manager.background_simulator_manager.get_session_status(session_id)
            
            logger.debug(f"Heartbeat: Session {session_id} simulator status from gRPC: {simulator_status_server}")
        else:
            logger.warning("Background simulator manager not available for heartbeat")

        # Prepare response
        response = {
            'type': 'heartbeat_ack',
            'timestamp': int(time.time() * 1000),
            'clientTimestamp': client_timestamp,
            'deviceId': device_id,
            'deviceIdValid': device_id_valid,
            'reason': reason,
            'simulatorStatus': simulator_status_server,
        }

        try:
            if not ws.closed:
                await ws.send_json(response)
                track_websocket_message("sent", "heartbeat_ack")

        except Exception as e:
            logger.error(f"Failed to send heartbeat_ack for client {client_id}: {e}")

        if not device_id_valid:
            await session_manager.state_manager.close(keep_simulator=True)