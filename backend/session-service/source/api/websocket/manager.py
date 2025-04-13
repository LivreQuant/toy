# source/websocket/manager.py
import json
import logging
import time
import asyncio
from typing import Dict, Set
from aiohttp import web, WSMsgType
from opentelemetry import trace

from source.api.websocket.utils import authenticate_websocket_request
from source.utils.tracing import optional_trace_span


class WebSocketManager:
    def __init__(self, session_manager, simulator_manager):
        self.session_manager = session_manager
        self.simulator_manager = simulator_manager
        self.tracer = trace.get_tracer("websocket_manager")
        self.logger = logging.getLogger('websocket_manager')

        # Track active connections
        self.active_connections: Set[web.WebSocketResponse] = set()

        # Register for exchange data
        self.session_manager.register_exchange_data_callback(self.broadcast_exchange_data)

    async def handle_connection(self, request: web.Request) -> web.WebSocketResponse:
        """
        Handle WebSocket connection lifecycle
        """
        with optional_trace_span(self.tracer, "websocket_connection") as span:
            # Authenticate user
            try:
                user_id, session_id, device_id = await authenticate_websocket_request(request, self.session_manager)
                span.set_attribute("user_id", user_id)
                span.set_attribute("device_id", device_id)
            except Exception as auth_error:
                self.logger.warning(f"WebSocket authentication failed: {auth_error}")
                return self._reject_connection(str(auth_error))

            # Create WebSocket
            ws = web.WebSocketResponse(heartbeat=10)
            await ws.prepare(request)

            # Add to active connections
            self.active_connections.add(ws)

            # Connection handler
            try:
                # Send connected message
                await self._send_connected(ws, user_id, device_id, session_id)

                # Process messages
                await self._connection_loop(ws, user_id, device_id)
            except Exception as e:
                self.logger.error(f"WebSocket connection error: {e}")
                await self._send_error(ws, "Unexpected connection error")
            finally:
                # Remove from active connections when done
                if ws in self.active_connections:
                    self.active_connections.remove(ws)

            return ws

    async def _connection_loop(self, ws: web.WebSocketResponse, user_id: str, device_id: str):
        """Main WebSocket message processing loop"""
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self._process_message(ws, user_id, device_id, msg.data)
                elif msg.type in (WSMsgType.CLOSING, WSMsgType.CLOSED):
                    break
        finally:
            await self._cleanup(ws)

    async def _process_message(self, ws: web.WebSocketResponse, user_id: str, device_id: str, raw_message: str):
        """Process incoming WebSocket messages"""
        try:
            message = json.loads(raw_message)
            message_type = message.get('type')

            handlers = {
                'heartbeat': self._handle_heartbeat,
                'start_simulator': self._handle_start_simulator,
                'stop_simulator': self._handle_stop_simulator,
                'reconnect': self._handle_reconnect
            }

            handler = handlers.get(message_type)
            if handler:
                await handler(ws, user_id, device_id, message)
            else:
                await self._send_error(ws, f"Unknown message type: {message_type}")

        except json.JSONDecodeError:
            await self._send_error(ws, "Invalid JSON")
        except Exception as e:
            await self._send_error(ws, str(e))

    async def _handle_heartbeat(self, ws, user_id, device_id, message):
        """Handle heartbeat message"""
        response = {
            'type': 'heartbeat_ack',
            'timestamp': int(time.time() * 1000)
        }
        await ws.send_json(response)

    async def _handle_start_simulator(self, ws, user_id, device_id, message):
        """Start simulator for user"""
        simulator_id, endpoint, error = await self.session_manager.start_simulator(user_id)

        if error:
            await self._send_error(ws, error)
        else:
            await ws.send_json({
                'type': 'simulator_started',
                'simulator_id': simulator_id,
                'endpoint': endpoint
            })

    async def _handle_stop_simulator(self, ws, user_id, device_id, message):
        """Stop user's simulator"""
        success, error = await self.session_manager.stop_simulator()

        if not success:
            await self._send_error(ws, error)
        else:
            await ws.send_json({
                'type': 'simulator_stopped'
            })

    async def _handle_reconnect(self, ws, user_id, device_id, message):
        """Handle reconnection"""
        # Update session metadata with device ID
        await self.session_manager.update_session_metadata({
            'device_id': device_id,
            'last_reconnect': time.time()
        })

        # Send reconnect result message
        await ws.send_json({
            'type': 'reconnect_result',
            'success': True,
            'message': 'Session reconnected successfully',
            'deviceId': device_id,
            'deviceIdValid': True,
            'sessionStatus': 'valid',
            'simulatorStatus': self._get_simulator_status()
        })

    def _get_simulator_status(self):
        """Get current simulator status"""
        return "RUNNING" if self.session_manager.simulator_active else "NONE"

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
        for ws in list(self.active_connections):
            if not ws.closed:
                send_tasks.append(asyncio.ensure_future(ws.send_json(payload)))

        if send_tasks:
            # Wait for all sends to complete
            await asyncio.gather(*send_tasks, return_exceptions=True)

    async def _send_connected(self, ws, user_id, device_id, session_id):
        """Send connected message to client"""
        payload = {
            'type': 'connected',
            'timestamp': int(time.time() * 1000),
            'userId': user_id,
            'deviceId': device_id,
            'sessionId': session_id
        }
        if not ws.closed:
            await ws.send_json(payload)

    async def _send_error(self, ws: web.WebSocketResponse, error_message: str):
        """Send error message to client"""
        if not ws.closed:
            await ws.send_json({
                'type': 'error',
                'message': error_message,
                'timestamp': int(time.time() * 1000)
            })

    async def _cleanup(self, ws: web.WebSocketResponse):
        """Cleanup resources when connection closes"""
        if ws in self.active_connections:
            self.active_connections.remove(ws)
        self.logger.info(f"WebSocket connection closed, remaining connections: {len(self.active_connections)}")

    def _reject_connection(self, reason: str) -> web.WebSocketResponse:
        """Reject WebSocket connection"""
        return web.WebSocketResponse(status=403, body=json.dumps({'error': reason}))
