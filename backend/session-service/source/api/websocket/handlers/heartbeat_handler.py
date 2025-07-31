"""
Handler for the 'heartbeat' WebSocket message type.
Simplified to only check connection status, not manage simulators.
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

        # Get session data
        session = await session_manager.get_session()

        if not session:
            logger.warning(f"Session not found for heartbeat from device {device_id}")

            response = {
                'type': 'heartbeat_ack',
                'timestamp': int(time.time() * 1000),
                'clientTimestamp': client_timestamp,
                'deviceId': device_id,
                'deviceIdValid': False,
                'reason': "Session not found",
                'simulatorStatus': "DISCONNECTED",
            }

            try:
                if not ws.closed:
                    await ws.send_json(response)
                    track_websocket_message("sent", "heartbeat_ack")
            except Exception as e:
                logger.error(f"Failed to send heartbeat_ack for client {client_id}: {e}")

            await session_manager.state_manager.close()
            return

        # Check session and device validity
        device_id_valid = True
        reason = ""
        
        if session.status != SessionStatus.ACTIVE:
            logger.info(f"Session {session.session_id} is no longer active")
            device_id_valid = False
            reason = "Session is no longer active"

        # Check device ID
        session_details = await session_manager.get_session_details()
        active_device_id = session_details.get('device_id') if session_details else None

        if active_device_id and active_device_id != device_id:
            logger.info(f"Device {device_id} is no longer active. Active device is {active_device_id}")
            device_id_valid = False
            reason = "Another device has connected with this account"

        # Update activity if valid
        if device_id_valid:
            await session_manager.update_session_activity()

        # Get simulator status
        simulator_status = session_manager.get_simulator_status()

        response = {
            'type': 'heartbeat_ack',
            'timestamp': int(time.time() * 1000),
            'clientTimestamp': client_timestamp,
            'deviceId': device_id,
            'deviceIdValid': device_id_valid,
            'reason': reason,
            'simulatorStatus': simulator_status,
        }

        try:
            if not ws.closed:
                await ws.send_json(response)
                track_websocket_message("sent", "heartbeat_ack")
        except Exception as e:
            logger.error(f"Failed to send heartbeat_ack for client {client_id}: {e}")

        if not device_id_valid:
            await session_manager.state_manager.close()