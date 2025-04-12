# websocket/manager.py
"""
WebSocket connection manager.
Handles WebSocket connection lifecycle orchestration.
Delegates authentication to authenticator.
Delegates connection state management to WebSocketRegistry.
Uses emitters for sending outgoing messages.
"""
import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional

from aiohttp import web, WSMsgType
from opentelemetry import trace, context

from source.config import config
from source.utils.event_bus import event_bus
from source.utils.metrics import track_websocket_connection_count, track_websocket_error
from source.utils.tracing import optional_trace_span

from source.core.session.manager import SessionManager
from source.core.stream.manager import StreamManager

# WebSocket Components
from source.api.websocket.authenticator import authenticate_websocket_request
from source.api.websocket.dispatcher import WebSocketDispatcher
from source.api.websocket.exceptions import WebSocketError
from source.api.websocket.registry import WebSocketRegistry

from source.api.websocket.emitters import connection_emitter, error_emitter

logger = logging.getLogger('websocket_manager')


class WebSocketManager:
    """Manages WebSocket connections lifecycle using registry, authenticator, and stream manager."""

    def __init__(self, session_manager: SessionManager, stream_manager: StreamManager):
        """Initialize WebSocket manager."""
        self.session_manager = session_manager
        self.stream_manager = stream_manager
        self.registry = WebSocketRegistry(session_manager=self.session_manager)

        self.dispatcher = WebSocketDispatcher(session_manager, self)
        self.cleanup_task = asyncio.create_task(self._cleanup_stale_connections(self.registry))
        self.tracer = trace.get_tracer("websocket_manager")

        # Subscribe to events
        event_bus.subscribe('exchange_data_received', self.handle_exchange_data)
        event_bus.subscribe('stream_error', self.handle_stream_error)
        event_bus.subscribe('simulator_ready', self.handle_simulator_ready)
        event_bus.subscribe('simulator_stopped', self.handle_simulator_stopped)
        event_bus.subscribe('connection_quality_updated', self.handle_connection_quality_update)

        track_websocket_connection_count(self.registry.get_total_connection_count())
        logger.info("WebSocketManager initialized with StreamManager.")

    async def handle_connection(self, request: web.Request) -> web.WebSocketResponse:
        """Handle incoming HTTP request, authentication, registration, and message loop."""

        with optional_trace_span(self.tracer, "handle_websocket_connection") as span:
            ws = web.WebSocketResponse(heartbeat=config.websocket.heartbeat_interval, autoping=True)
            try:
                await ws.prepare(request)
            except Exception as prepare_err:
                logger.error(f"WebSocket prepare failed: {prepare_err}", exc_info=True)
                return web.Response(status=400, text=f"WebSocket handshake failed: {prepare_err}")

            device_id_from_query = request.query.get('deviceId')
            if device_id_from_query: span.set_attribute("device_id_query", device_id_from_query)

            try:
                # Pass self (WebSocketManager) instead of session_manager
                user_id, session_id, device_id = await authenticate_websocket_request(request, self)
                span.set_attribute("user_id", str(user_id))
                span.set_attribute("session_id", session_id)
                span.set_attribute("device_id", device_id)
            except WebSocketError as e:
                logger.warning(f"WebSocket connection rejected: {e.error_code} - {e.message}")
                return await self._close_with_error(ws, span, e.message, code=4001, error_code=e.error_code,
                                                    exception=e)
            except Exception as e:
                logger.error(f"Unexpected error during WebSocket authentication: {e}", exc_info=True)
                return await self._close_with_error(ws, span, "Internal server error during authentication", code=5000,
                                                    error_code="AUTH_UNEXPECTED_ERROR", exception=e)

            client_id = request.query.get('clientId', f"client-{time.time_ns()}")
            span.set_attribute("client_id", client_id)

            registered = await self.registry.register(ws, session_id=session_id, user_id=user_id, client_id=client_id,
                                                      device_id=device_id)
            if not registered:
                logger.error(f"Failed to register authenticated websocket: client {client_id}, session {session_id}")
                return await self._close_with_error(ws, span, "Failed to register connection state", code=5000,
                                                    error_code="REGISTRATION_FAILED")

            await connection_emitter.send_connected(ws, client_id=client_id, device_id=device_id, session_id=session_id)

            # Publish event about new connection
            await event_bus.publish('ws_connection_established',
                                    session_id=session_id,
                                    client_id=client_id,
                                    user_id=user_id)

            try:
                async for msg in ws:
                    # ... (message loop remains the same) ...
                    if msg.type == WSMsgType.TEXT:
                        self.registry.update_connection_activity(ws)
                        await self.dispatcher.dispatch_message(ws, session_id, user_id, client_id, msg.data)
                    elif msg.type == WSMsgType.ERROR:
                        logger.error(f"WS error: session={session_id}, client={client_id}: {ws.exception()}")
                        track_websocket_error("AIOHTTP_CONNECTION_ERROR")
                        break
                    elif msg.type in (WSMsgType.CLOSING, WSMsgType.CLOSED):
                        logger.info(f"WS closing/closed by client: session={session_id}, client={client_id}")
                        break
            except asyncio.CancelledError:
                logger.info(f"WS message loop cancelled: session={session_id}, client={client_id}")
                raise
            except Exception as e:
                logger.error(f"Error processing WS messages: session={session_id}, client={client_id}: {e}",
                             exc_info=True)
                await error_emitter.send_error(ws=ws, error_code="MESSAGE_PROCESSING_ERROR",
                                               message="Internal server error during message processing.", span=span,
                                               exception=e)
            finally:
                logger.debug(f"Entering finally block for WS: session={session_id}, client={client_id}")
                await self._unregister_connection_and_cleanup(ws)

            logger.info(f"WS connection handler finished: session={session_id}, client={client_id}")
            return ws

    async def _unregister_connection_and_cleanup(self, ws: web.WebSocketResponse):
        """Calls registry to unregister and publishes disconnection event"""
        session_id, client_id, session_became_empty = await self.registry.unregister(ws)
        if session_id is not None:
            logger.info(
                f"Unregistered client {client_id} from session {session_id}. Session empty: {session_became_empty}")

            # Publish event about client disconnection
            await event_bus.publish(
                'ws_connection_closed',
                session_id=session_id,
                client_id=client_id,
                session_empty=session_became_empty
            )

    async def _close_with_error(self, ws: web.WebSocketResponse, span: Optional[trace.Span], error_msg: str, *,
                                code: int, error_code: str,
                                exception: Optional[Exception] = None) -> web.WebSocketResponse:
        active_context = context.get_current()
        current_span = trace.get_current_span(active_context)
        logger.warning(f"Closing WS connection: {error_msg} (Code: {code}, ErrorCode: {error_code})")
        await error_emitter.send_error(ws=ws, error_code=error_code, message=error_msg, span=current_span,
                                       exception=exception)
        try:
            if not ws.closed: await ws.close(code=code, message=error_msg.encode('utf-8'))
        except Exception as e:
            logger.error(f"Error closing WS after sending error '{error_code}': {e}")
        return ws

    async def broadcast_to_session(self, session_id: str, message: Any):
        """Broadcast a message to all clients in a session"""
        connections_to_send = list(self.registry.get_session_connections(session_id))
        if not connections_to_send:
            return

        if isinstance(message, dict):
            data = json.dumps(message)
            message_type = message.get('type', 'unknown')
        else:
            data = str(message)
            message_type = 'raw_string'

        logger.debug(f"Broadcasting '{message_type}' to {len(connections_to_send)} clients in session {session_id}")

        tasks = [self._send_to_websocket(ws, data, session_id) for ws in connections_to_send if not ws.closed]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                ws_error = connections_to_send[i]
                conn_info = self.registry.get_connection_info(ws_error)
                client_id = conn_info.get('client_id', 'unknown') if conn_info else 'unknown'
                logger.error(f"Error broadcasting to client {client_id} in session {session_id}: {result}")

    async def _send_to_websocket(self, ws: web.WebSocketResponse, data: str, session_id: str) -> None:
        """Send data to a websocket with error handling"""
        try:
            if not ws.closed:
                await ws.send_str(data)
        except ConnectionResetError:
            logger.warning(f"Connection reset sending to client in session {session_id}.")
        except Exception as e:
            conn_info = self.registry.get_connection_info(ws)
            client_id = conn_info.get('client_id', 'unknown') if conn_info else 'unknown'
            logger.error(f"Failed to send message to client {client_id} in session {session_id}: {e}")
            raise

    # --- Event handlers ---

    async def handle_exchange_data(self, session_id: str, data: Dict[str, Any]):
        """Handle exchange data event by broadcasting to session clients"""
        await self.broadcast_to_session(session_id, {
            'type': 'exchange_data',
            'data': data
        })

    async def handle_stream_error(self, session_id: str, error: str, **kwargs):
        """Handle stream error event by notifying session clients"""
        await self.broadcast_to_session(session_id, {
            'type': 'stream_error',
            'error': error
        })

    async def handle_simulator_ready(self, session_id: str, endpoint: str):
        """Handle simulator ready event by notifying session clients"""
        await self.broadcast_to_session(session_id, {
            'type': 'simulator_status',
            'status': 'RUNNING',
            'endpoint': endpoint
        })

    async def handle_simulator_stopped(self, session_id: str, simulator_id: str):
        """Handle simulator stopped event by notifying session clients"""
        await self.broadcast_to_session(session_id, {
            'type': 'simulator_status',
            'status': 'STOPPED',
            'simulator_id': simulator_id
        })

    async def handle_connection_quality_update(self, session_id: str, quality: str, reconnect_recommended: bool):
        """Handle connection quality update by notifying clients"""
        await self.broadcast_to_session(session_id, {
            'type': 'connection_quality',
            'quality': quality,
            'reconnect_recommended': reconnect_recommended
        })

    async def close_all_connections(self, reason="Server shutting down"):
        """Gracefully close all managed WebSocket connections and publish shutdown event"""
        connection_count = self.registry.get_total_connection_count()
        logger.info(f"Closing all ({connection_count}) WebSocket connections: {reason}")

        # Publish shutdown event
        await event_bus.publish('server_shutting_down', reason=reason)

        close_tasks = []
        all_websockets = self.registry.get_all_websockets()

        for ws in all_websockets:
            if not ws.closed:
                await connection_emitter.send_shutdown(ws, reason)
                close_tasks.append(ws.close(code=1001, message=reason.encode('utf-8')))

        await asyncio.gather(*close_tasks, return_exceptions=True)
        logger.info("Finished sending close() command to all websockets.")

        # Clear registry state
        self.registry.clear()

        logger.info("All WebSocket connections closed and resources cleaned up.")

    async def _cleanup_stale_connections(self, registry: WebSocketRegistry):
        """Periodically check for and clean up stale connections"""
        await asyncio.sleep(15)
        while True:
            try:
                await asyncio.sleep(config.websocket.heartbeat_interval)
                current_time = time.time()
                stale_connections_ws = []
                timeout_threshold = (config.websocket.heartbeat_interval * 3) + 10

                for ws, info in list(registry.get_all_connection_info_items()):
                    last_activity = info.get('last_activity', info.get('connected_at', current_time))
                    inactive_time = current_time - last_activity

                    if ws.closed:
                        stale_connections_ws.append(ws)
                    elif inactive_time > timeout_threshold:
                        stale_connections_ws.append(ws)
                        logger.warning(
                            f"Marking WS as stale: session={info.get('session_id')}, client={info.get('client_id')}, "
                            f"inactive for {inactive_time:.1f}s")

                if stale_connections_ws:
                    logger.info(f"Cleaning up {len(stale_connections_ws)} stale/closed WebSocket connections")
                    unregister_tasks = []

                    for ws in stale_connections_ws:
                        if not ws.closed:
                            # Send timeout message before closing
                            await connection_emitter.send_timeout(ws)
                            try:
                                await ws.close(code=1008, message=b'Policy violation - inactive')
                            except Exception as e:
                                logger.error(f"Error closing stale connection: {e}")

                        # Unregister the connection
                        unregister_tasks.append(self._unregister_connection_and_cleanup(ws))

                    await asyncio.gather(*unregister_tasks, return_exceptions=True)

            except asyncio.CancelledError:
                logger.info("Cleanup task cancelled.")
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def register_activity(self, session_id: str) -> None:
        """
        Register activity for a session and update last activity.

        Args:
            session_id: The session ID to update activity for
        """
        # Update session activity through session manager
        await self.session_manager.update_session_activity(session_id)
