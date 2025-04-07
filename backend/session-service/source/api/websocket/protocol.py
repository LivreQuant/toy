# source/api/websocket/protocol.py
"""
WebSocket protocol handler for the session service.
Implements the simplified messaging protocol defined in the design document.
"""
import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, List

from opentelemetry import trace

from source.models.session import SessionStatus, ConnectionQuality
from source.models.simulator import SimulatorStatus
from source.utils.metrics import track_websocket_message, track_websocket_error
from source.utils.tracing import optional_trace_span

logger = logging.getLogger('websocket_protocol')


class WebSocketProtocol:
    """Handles WebSocket message processing according to the defined protocol"""

    def __init__(self, session_manager, websocket_manager):
        """
        Initialize the protocol handler

        Args:
            session_manager: The session manager instance
            websocket_manager: The WebSocket manager instance
        """
        self.session_manager = session_manager
        self.ws_manager = websocket_manager
        self.tracer = trace.get_tracer("websocket_protocol")

        # Define message type handlers
        self.message_handlers = {
            'heartbeat': self.handle_heartbeat,
            'reconnect': self.handle_reconnect
        }

        # Track active exchange data streams
        self.exchange_data_streams = {}  # session_id -> streaming task

    async def process_message(self, ws, session_id, user_id, client_id, data):
        """
        Process an incoming WebSocket message

        Args:
            ws: The WebSocket connection
            session_id: Session ID
            user_id: User ID
            client_id: Client ID
            data: Message data (string or dict)
        """
        with optional_trace_span(self.tracer, "process_websocket_message") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("client_id", client_id)

            try:
                # Parse message if it's a string
                if isinstance(data, str):
                    message = json.loads(data)
                else:
                    message = data

                message_type = message.get('type')
                span.set_attribute("message_type", message_type)
                track_websocket_message("received", message_type or "unknown")

                if not message_type:
                    await ws.send_json({
                        'type': 'error',
                        'message': 'Missing message type'
                    })
                    track_websocket_error("missing_type")
                    return

                # Update session activity on any valid message
                await self.session_manager.update_session_activity(session_id)

                # Process message based on type
                handler = self.message_handlers.get(message_type)
                if handler:
                    await handler(ws, session_id, user_id, client_id, message)
                else:
                    logger.warning(f"Unknown message type: {message_type}")
                    await ws.send_json({
                        'type': 'error',
                        'message': f'Unknown message type: {message_type}'
                    })
                    track_websocket_error("unknown_type")

            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in WebSocket message: {data[:100]}")
                span.set_attribute("error", "Invalid JSON")
                await ws.send_json({
                    'type': 'error',
                    'message': 'Invalid JSON message'
                })
                track_websocket_error("invalid_json")
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}", exc_info=True)
                span.record_exception(e)
                await ws.send_json({
                    'type': 'error',
                    'message': 'Internal server error'
                })
                track_websocket_error("processing_error")

    async def handle_heartbeat(self, ws, session_id, user_id, client_id, message):
        """
        Handle heartbeat message from client

        Args:
            ws: The WebSocket connection
            session_id: Session ID
            user_id: User ID
            client_id: Client ID
            message: The heartbeat message
        """
        with optional_trace_span(self.tracer, "handle_heartbeat") as span:
            span.set_attribute("session_id", session_id)

            # Extract values from message
            timestamp = message.get('timestamp', int(time.time() * 1000))
            device_id = message.get('deviceId')
            connection_quality = message.get('connectionQuality', 'good')
            session_status = message.get('sessionStatus', 'active')
            simulator_status = message.get('simulatorStatus', 'none')

            span.set_attribute("client_timestamp", timestamp)
            span.set_attribute("device_id", device_id)

            # Verify device ID is valid for this session
            session = await self.session_manager.get_session(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found during heartbeat")
                await ws.send_json({
                    'type': 'heartbeat_ack',
                    'timestamp': int(time.time() * 1000),
                    'clientTimestamp': timestamp,
                    'deviceId': device_id,
                    'deviceIdValid': False,
                    'connectionQualityUpdate': connection_quality,
                    'sessionStatus': 'invalid',
                    'simulatorStatus': 'none'
                })
                return

            # Get device ID from metadata
            metadata = session.get('metadata', {})
            current_device_id = getattr(metadata, 'device_id', None)
            device_id_valid = current_device_id == device_id

            # Get current simulator status (using string values to avoid enum issues)
            simulator_status_server = getattr(metadata, 'simulator_status', 'none')

            # Respond with heartbeat acknowledgment
            response = {
                'type': 'heartbeat_ack',
                'timestamp': int(time.time() * 1000),
                'clientTimestamp': timestamp,
                'deviceId': current_device_id,
                'deviceIdValid': device_id_valid,
                'connectionQualityUpdate': connection_quality,
                'sessionStatus': 'valid' if device_id_valid else 'invalid',
                'simulatorStatus': simulator_status_server
            }

            # Send response
            await ws.send_json(response)
            track_websocket_message("sent", "heartbeat_ack")

            # If device ID is invalid, client will auto-disconnect
            if not device_id_valid:
                logger.info(f"Invalid device ID in heartbeat: {device_id}, expected: {current_device_id}")
                span.set_attribute("error", "Invalid device ID")

    async def handle_reconnect(self, ws, session_id, user_id, client_id, message):
        """
        Handle reconnect message from client

        Args:
            ws: The WebSocket connection
            session_id: Session ID
            user_id: User ID
            client_id: Client ID
            message: The reconnect message
        """
        with optional_trace_span(self.tracer, "handle_reconnect") as span:
            span.set_attribute("session_id", session_id)

            # Extract values from message
            device_id = message.get('deviceId')
            session_token = message.get('sessionToken')
            request_id = message.get('requestId', 'unknown')

            span.set_attribute("device_id", device_id)
            span.set_attribute("request_id", request_id)

            if not device_id or not session_token:
                await ws.send_json({
                    'type': 'reconnect_result',
                    'requestId': request_id,
                    'success': False,
                    'message': 'Missing deviceId or sessionToken'
                })
                track_websocket_message("sent", "reconnect_result_failure")
                return

            # Validate session and device ID
            valid_user_id = await self.session_manager.validate_session(session_id, session_token, device_id)
            if not valid_user_id:
                await ws.send_json({
                    'type': 'reconnect_result',
                    'requestId': request_id,
                    'success': False,
                    'deviceIdValid': False,
                    'message': 'Invalid session, token or device ID'
                })
                track_websocket_message("sent", "reconnect_result_failure")
                return

            # Get session to access metadata
            session = await self.session_manager.get_session(session_id)
            if not session:
                await ws.send_json({
                    'type': 'reconnect_result',
                    'requestId': request_id,
                    'success': False,
                    'message': 'Session not found'
                })
                track_websocket_message("sent", "reconnect_result_failure")
                return

            # Extract metadata
            metadata = session.get('metadata', {})
            simulator_status = getattr(metadata, 'simulator_status', 'none')

            # Respond with reconnect result
            response = {
                'type': 'reconnect_result',
                'requestId': request_id,
                'success': True,
                'deviceId': device_id,
                'deviceIdValid': True,
                'message': 'Session reconnected successfully',
                'sessionStatus': 'valid',
                'simulatorStatus': simulator_status
            }

            # Send response
            await ws.send_json(response)
            track_websocket_message("sent", "reconnect_result_success")

    async def send_exchange_data_update(self, session_id, data):
        """
        Send exchange data update to clients

        Args:
            session_id: The session ID
            data: The exchange data to send
        """
        # Format exchange data update according to design spec
        exchange_update = {
            'type': 'exchange_data_status',
            'timestamp': int(time.time() * 1000),
            'symbols': data.get('symbols', {}),
            'userOrders': data.get('userOrders', {}),
            'userPositions': data.get('userPositions', {})
        }

        # Broadcast to all clients for this session
        await self.ws_manager.broadcast_to_session(session_id, exchange_update)

    async def stop_exchange_data_stream(self, session_id):
        """
        Stop exchange data stream for a session

        Args:
            session_id: The session ID
        """
        if session_id in self.exchange_data_streams:
            task = self.exchange_data_streams[session_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
            del self.exchange_data_streams[session_id]
            logger.info(f"Stopped exchange data stream for session {session_id}")