# source/websocket/manager.py
import json
import logging
import time
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

            # Connection handler
            try:
                await self._connection_loop(ws, user_id, device_id)
            except Exception as e:
                self.logger.error(f"WebSocket connection error: {e}")
                await self._send_error(ws, "Unexpected connection error")

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
        # Implement reconnection logic using session_manager
        pass

    async def _send_error(self, ws: web.WebSocketResponse, error_message: str):
        """Send error message to client"""
        await ws.send_json({
            'type': 'error',
            'message': error_message
        })

    async def _cleanup(self, ws: web.WebSocketResponse):
        """Cleanup resources when connection closes"""
        # Implement any necessary cleanup
        pass

    def _reject_connection(self, reason: str) -> web.WebSocketResponse:
        """Reject WebSocket connection"""
        return web.WebSocketResponse(status=403, body=json.dumps({'error': reason}))
