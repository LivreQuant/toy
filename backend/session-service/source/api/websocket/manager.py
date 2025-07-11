# backend/session-service/source/api/websocket/manager.py
"""
WebSocket manager with enhanced status tracking via gRPC.
"""
import json
import logging
import time
import asyncio
from typing import Dict, Any
from aiohttp import web, WSMsgType
from opentelemetry import trace

from source.api.websocket.utils import authenticate_websocket_request
from source.utils.tracing import optional_trace_span
from source.utils.metrics import track_websocket_message
from source.api.websocket.dispatcher import WebSocketDispatcher
from source.api.websocket.emitters import error_emitter

from source.models.exchange_data import ExchangeDataUpdate


class WebSocketManager:
    def __init__(self, session_manager):
        self.session_manager = session_manager
        self.tracer = trace.get_tracer("websocket_manager")
        self.logger = logging.getLogger('websocket_manager')

        # Enhanced connection tracking
        self.active_connections: Dict[str, web.WebSocketResponse] = {}  # device_id -> ws
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}  # device_id -> metadata

        # Create a dispatcher instance
        self.dispatcher = WebSocketDispatcher(session_manager)

        # Register for exchange data
        self.session_manager.register_exchange_data_callback(self.broadcast_exchange_data)

    async def handle_connection(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connection lifecycle"""
        self.logger.info(f"WebSocket connection request received from {request.remote}")
        self.logger.info(f"Headers: {dict(request.headers)}")
        self.logger.info(f"Query params: {dict(request.query)}")

        with (optional_trace_span(self.tracer, "websocket_connection") as span):
            # Authenticate user and check for device conflicts
            try:
                self.logger.info(f"WebSocket connection request received from {request.remote}")

                user_id, device_id = await authenticate_websocket_request(request, self.session_manager)
                client_id = f"{device_id}-{time.time_ns()}"

                # Check if the user already has an active session
                session = await self.session_manager.get_session()
                if session:
                    # Get existing device ID
                    session_details = await self.session_manager.get_session_details()
                    existing_device_id = session_details.get('device_id') if session_details else None

                    # If different device ID, mark this as the new active device
                    if existing_device_id and existing_device_id != device_id:
                        self.logger.info(
                            f"User {user_id} connecting with new device {device_id}, replacing {existing_device_id}")
                        request['previous_device_id'] = existing_device_id

                        # Update session details with the new device ID
                        await self.session_manager.update_session_details({
                            'device_id': device_id,
                            'last_device_update': time.time()
                        })

            except Exception as auth_error:
                self.logger.warning(f"WebSocket authentication failed: {auth_error}")
                return self._reject_connection(str(auth_error))

            # Create WebSocket
            ws = web.WebSocketResponse(heartbeat=10)
            await ws.prepare(request)

            # Handle device replacement if needed
            if request.get('previous_device_id'):
                previous_device_id = request['previous_device_id']
                self.logger.warning(f"Device {device_id} is replacing existing device {previous_device_id}")

                # Find the old connection for this device
                old_ws = self.active_connections.get(previous_device_id)
                if old_ws and not old_ws.closed:
                    self.logger.info(f"Closing connection for replaced device {previous_device_id}")
                    # Force close the old connection
                    try:
                        await old_ws.close(code=1000, message=b"Connection replaced by new device")
                    except Exception as e:
                        self.logger.error(f"Error closing old connection: {e}")

                    # Remove old connection
                    if previous_device_id in self.active_connections:
                        del self.active_connections[previous_device_id]
                    if previous_device_id in self.connection_metadata:
                        del self.connection_metadata[previous_device_id]

            # Add to active connections
            self.active_connections[device_id] = ws
            self.connection_metadata[device_id] = {
                'user_id': user_id,
                'client_id': client_id,
                'connected_at': time.time(),
                'last_activity': time.time()
            }

            # Connection handler
            try:
                # Process messages - use the existing method name from your codebase
                await self._connection_loop(ws, user_id, device_id, client_id)
            except Exception as e:
                self.logger.error(f"WebSocket connection error: {e}")
                await error_emitter.send_error(
                    ws=ws,
                    error_code="CONNECTION_ERROR",
                    message="Unexpected connection error"
                )
            finally:
                # Remove from active connections when done
                if device_id in self.active_connections and self.active_connections[device_id] is ws:
                    del self.active_connections[device_id]
                    if device_id in self.connection_metadata:
                        del self.connection_metadata[device_id]

            return ws
        
    async def _connection_loop(self, ws: web.WebSocketResponse, user_id: str, device_id: str, client_id: str):
        """Handle incoming WebSocket messages until connection closes"""
        try:
            self.logger.info(f"Starting message processing loop for client {client_id}")
            
            # Process messages until connection is closed
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    # Update last activity timestamp
                    if device_id in self.connection_metadata:
                        self.connection_metadata[device_id]['last_activity'] = time.time()
                    
                    # Process the message
                    await self.dispatcher.dispatch_message(
                        ws=ws,
                        user_id=user_id,
                        client_id=client_id,
                        device_id=device_id,
                        raw_data=msg.data
                    )
                elif msg.type == WSMsgType.ERROR:
                    self.logger.error(f"WebSocket connection closed with error: {ws.exception()}")
                    break
                elif msg.type == WSMsgType.CLOSE:
                    self.logger.info(f"WebSocket connection closing: {msg.data}")
                    break
        except Exception as e:
            self.logger.error(f"Error in WebSocket message loop for client {client_id}: {e}")
        finally:
            # Cleanup resources when connection ends
            await self._cleanup(ws, device_id)
            self.logger.info(f"WebSocket connection closed for client {client_id}")
            
    async def _cleanup(self, ws: web.WebSocketResponse, device_id: str):
        """Cleanup resources when connection closes"""
        if device_id in self.active_connections and self.active_connections[device_id] is ws:
            del self.active_connections[device_id]
            if device_id in self.connection_metadata:
                del self.connection_metadata[device_id]

        self.logger.info(
            f"WebSocket connection for device {device_id} closed, remaining connections: {len(self.active_connections)}")

        # If all connections are closed, reset the session state
        if len(self.active_connections) == 0:
            self.logger.info("All connections closed, resetting session state to ready")
            try:
                # First stop any active streams
                if self.session_manager.stream_manager:
                    try:
                        session_id = self.session_manager.state_manager.get_active_session_id()
                        if session_id:
                            await self.session_manager.stream_manager.stop_stream(session_id)
                    except Exception as e:
                        self.logger.error(f"Error stopping streams during cleanup: {e}")

                # Reset session state but preserve simulators
                await self.session_manager.state_manager.close(keep_simulator=True)
                await self.session_manager.cleanup_session(keep_simulator=True)
            except Exception as e:
                self.logger.error(f"Error resetting session state during connection cleanup: {e}")

    async def broadcast_exchange_data(self, data: ExchangeDataUpdate):
        """Broadcast exchange data to all active WebSocket clients using standardized format"""
        if not self.active_connections:
            return

        # Create a unique ID for this broadcast
        data_id = f"{data.timestamp}-{data.update_id}"
        self.logger.info(
            f"WebSocketManager broadcasting exchange data [ID: {data_id}] to {len(self.active_connections)} clients"
        )

        # Create message payload
        payload = {
            'type': 'exchange_data',
            'timestamp': int(time.time() * 1000),
            'data': data.to_dict()  # Use the standardized to_dict method
        }

        # Send to all active connections
        send_tasks = []
        for device_id, ws in list(self.active_connections.items()):
            if not ws.closed:
                send_tasks.append(asyncio.ensure_future(ws.send_json(payload)))

        if send_tasks:
            # Wait for all sends to complete
            await asyncio.gather(*send_tasks, return_exceptions=True)
            self.logger.debug(f"Completed sending exchange data [ID: {data_id}] to {len(send_tasks)} clients")

        # Track this message
        track_websocket_message("sent_broadcast", "exchange_data")

    async def broadcast_to_session(self, payload: Dict[str, Any]) -> int:
        """
        Broadcast a message to all devices connected to a session.
        
        Args:
            payload: The message payload
            
        Returns:
            Number of clients the message was sent to
        """
        if not self.active_connections:
            return 0

        # Get all device connections for this session
        sent_count = 0

        # In singleton mode, all connections belong to the same session
        for device_id, ws in list(self.active_connections.items()):
            if not ws.closed:
                try:
                    await ws.send_json(payload)
                    sent_count += 1
                    self.logger.debug(f"Sent status update to device {device_id}: {payload.get('type', 'unknown')}")
                except Exception as e:
                    self.logger.error(f"Error sending to device {device_id}: {e}")

        track_websocket_message("sent_broadcast", payload.get('type', 'unknown'))
        return sent_count

    def _reject_connection(self, reason: str) -> web.Response:
        """Reject WebSocket connection"""
        return web.Response(
            status=403,
            text=json.dumps({'error': reason}),
            content_type='application/json'
        )

    async def broadcast_to_device(self, device_id: str, payload: Dict[str, Any]) -> bool:
        """Send a message to a specific device"""
        if device_id not in self.active_connections:
            return False

        ws = self.active_connections[device_id]
        if ws.closed:
            return False

        try:
            await ws.send_json(payload)
            track_websocket_message("sent", payload.get('type', 'unknown'))
            return True
        except Exception as e:
            self.logger.error(f"Error sending message to device {device_id}: {e}")
            return False

    def get_connected_devices(self) -> list:
        """Get list of connected devices"""
        return list(self.active_connections.keys())

    def get_session_connections(self) -> list:
        """Get all active connections for the current session"""
        return list(self.active_connections.values())

    def get_device_connection_info(self, device_id: str) -> Dict[str, Any]:
        """Get connection info for a device"""
        if device_id not in self.connection_metadata:
            return {}
        return self.connection_metadata[device_id]

    def get_connection_count(self) -> int:
        """Get total number of active connections"""
        return len(self.active_connections)

    async def close_all_connections(self, reason: str = "Service shutting down"):
        """Close all active connections with a message"""
        if not self.active_connections:
            return

        close_tasks = []
        for device_id, ws in list(self.active_connections.items()):
            if not ws.closed:
                # Add close task
                close_tasks.append(ws.close(code=1000, message=reason.encode('utf-8')))

        # Wait for all connections to close
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)

        # Clear tracking
        self.active_connections.clear()
        self.connection_metadata.clear()