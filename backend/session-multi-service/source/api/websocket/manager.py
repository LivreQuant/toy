# source/api/websocket/manager.py
import json
import logging
import time
import asyncio
from typing import Dict, Any, Set
from aiohttp import web, WSMsgType
from opentelemetry import trace

from source.api.websocket.utils import authenticate_websocket_request
from source.utils.tracing import optional_trace_span
from source.utils.metrics import track_websocket_message
from source.api.websocket.dispatcher import WebSocketDispatcher
from source.api.websocket.emitters import error_emitter, connection_emitter


class WebSocketManager:
    def __init__(self, session_manager, simulator_manager):
        self.session_manager = session_manager
        self.simulator_manager = simulator_manager
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
        """
        Handle WebSocket connection lifecycle
        """
        with optional_trace_span(self.tracer, "websocket_connection") as span:
            # Authenticate user - this now checks for device ID conflicts
            try:
                user_id, session_id, device_id = await authenticate_websocket_request(request, self.session_manager)
                span.set_attribute("user_id", user_id)
                span.set_attribute("device_id", device_id)
                client_id = f"{device_id}-{time.time_ns()}"
                span.set_attribute("client_id", client_id)
            except Exception as auth_error:
                self.logger.warning(f"WebSocket authentication failed: {auth_error}")
                return self._reject_connection(str(auth_error))

            # Check if device already has an active connection
            if device_id in self.active_connections:
                old_ws = self.active_connections[device_id]
                if not old_ws.closed:
                    self.logger.warning(f"Device {device_id} already has an active connection. Closing old connection.")
                    await connection_emitter.send_connection_replaced(old_ws)
                    # Force close the old connection
                    await old_ws.close(code=1000, message=b"Connection replaced by new device connection")
                
                # Remove old connection
                del self.active_connections[device_id]
                if device_id in self.connection_metadata:
                    del self.connection_metadata[device_id]

            # Create WebSocket
            ws = web.WebSocketResponse(heartbeat=10)
            await ws.prepare(request)

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
                # Send connected message
                await connection_emitter.send_connected(
                    ws, 
                    client_id=client_id,
                    device_id=device_id,
                    session_id=session_id
                )

                # Process messages
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
        """Main WebSocket message processing loop"""
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    # Update last activity time
                    if device_id in self.connection_metadata:
                        self.connection_metadata[device_id]['last_activity'] = time.time()
                        
                    # Use the dispatcher to handle the message
                    await self.dispatcher.dispatch_message(ws, user_id, client_id, msg.data)
                elif msg.type in (WSMsgType.CLOSING, WSMsgType.CLOSED):
                    break
        finally:
            await self._cleanup(ws, device_id)

    async def broadcast_exchange_data(self, data):
        """Broadcast exchange data to all active WebSocket clients"""
        if not self.active_connections:
            return

        # Create message payload
        payload = {
            'type': 'exchange_data',
            'timestamp': int(time.time() * 1000),
            'data': data
        }

        # Send to all active connections
        send_tasks = []
        for device_id, ws in list(self.active_connections.items()):
            if not ws.closed:
                send_tasks.append(asyncio.ensure_future(ws.send_json(payload)))

        if send_tasks:
            # Wait for all sends to complete
            await asyncio.gather(*send_tasks, return_exceptions=True)

    async def broadcast_to_session(self, session_id: str, payload: Dict[str, Any]) -> int:
        """
        Broadcast a message to all devices connected to a session.
        
        Args:
            session_id: The session ID
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
                except Exception as e:
                    self.logger.error(f"Error sending to device {device_id}: {e}")
                    
        track_websocket_message("sent_broadcast", payload.get('type', 'unknown'))
        return sent_count

    async def _cleanup(self, ws: web.WebSocketResponse, device_id: str):
        """Cleanup resources when connection closes"""
        if device_id in self.active_connections and self.active_connections[device_id] is ws:
            del self.active_connections[device_id]
            if device_id in self.connection_metadata:
                del self.connection_metadata[device_id]
        
        self.logger.info(f"WebSocket connection for device {device_id} closed, remaining connections: {len(self.active_connections)}")

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
                # Send shutdown message
                try:
                    await connection_emitter.send_shutdown(ws, reason)
                except Exception:
                    pass
                    
                # Add close task
                close_tasks.append(ws.close(code=1000, message=reason.encode('utf-8')))
                
        # Wait for all connections to close
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)
            
        # Clear tracking
        self.active_connections.clear()
        self.connection_metadata.clear()