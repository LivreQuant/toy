# websocket/manager.py
"""
WebSocket connection manager for single-user mode.
Handles WebSocket connections and message dispatching.
"""
import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, List

from aiohttp import web, WSMsgType
from opentelemetry import trace, context

from source.config import config
from source.utils.event_bus import event_bus
from source.utils.metrics import track_websocket_connection_count, track_websocket_error
from source.utils.tracing import optional_trace_span

from source.core.session.manager import SessionManager
from source.core.stream.manager import StreamManager

# WebSocket Components
from source.api.websocket.utils import authenticate_websocket_request
from source.api.websocket.dispatcher import WebSocketDispatcher 
from source.api.websocket.exceptions import WebSocketError

from source.api.websocket.emitters import connection_emitter, error_emitter

logger = logging.getLogger('websocket_manager')


class WebSocketManager:
    """Manages WebSocket connections in single-user mode."""

    def __init__(self, session_manager: SessionManager, stream_manager: StreamManager, 
                 singleton_mode: bool = False, singleton_session_id: str = None):
        """Initialize WebSocket manager."""
        self.session_manager = session_manager
        self.stream_manager = stream_manager
        
        # Singleton mode settings
        self.singleton_mode = singleton_mode
        self.singleton_session_id = singleton_session_id

        # In single-user mode, we keep a simple list of active connections
        self._active_connections: List[web.WebSocketResponse] = []
        
        # Create dispatcher 
        self.dispatcher = WebSocketDispatcher(session_manager)

        self.cleanup_task = asyncio.create_task(self._cleanup_stale_connections())
        self.tracer = trace.get_tracer("websocket_manager")

        # Subscribe to events
        event_bus.subscribe('exchange_data_received', self.handle_exchange_data)
        event_bus.subscribe('stream_error', self.handle_stream_error)
        event_bus.subscribe('simulator_ready', self.handle_simulator_ready)
        event_bus.subscribe('simulator_stopped', self.handle_simulator_stopped)
        event_bus.subscribe('connection_quality_updated', self.handle_connection_quality_update)

        logger.info(f"WebSocketManager initialized in {'singleton' if singleton_mode else 'multi-user'} mode")

    async def handle_connection(self, request: web.Request) -> web.WebSocketResponse:
        """Handle incoming HTTP request, authentication, and message loop."""

        with optional_trace_span(self.tracer, "handle_websocket_connection") as span:
            # Check if service is ready for new connections - if not, reject immediately
            state_manager = request.app['state_manager']

            if not state_manager.is_ready() and state_manager.is_active():
                logger.warning("Rejecting connection - service is already handling a user session")
                return web.Response(
                    status=503,  # Service Unavailable
                    text="This session service instance is already handling a user session",
                    content_type="text/plain"
                )

            ws = web.WebSocketResponse(heartbeat=config.websocket.heartbeat_interval, autoping=True)
            try:
                await ws.prepare(request)
            except Exception as prepare_err:
                logger.error(f"WebSocket prepare failed: {prepare_err}", exc_info=True)
                return web.Response(status=400, text=f"WebSocket handshake failed: {prepare_err}")

            # In singleton mode, get the session ID from the session manager
            if self.session_manager.singleton_mode:
                session_id = self.session_manager.singleton_session_id

                # Authenticate user
                try:
                    user_id, _, device_id = await authenticate_websocket_request(request, self.session_manager)
                except WebSocketError as e:
                    logger.warning(f"WebSocket connection rejected: {e.error_code} - {e.message}")
                    return await self._close_with_error(ws, span, e.message, code=4001, error_code=e.error_code,
                                                        exception=e)
                except Exception as e:
                    logger.error(f"Unexpected error during WebSocket authentication: {e}", exc_info=True)
                    return await self._close_with_error(ws, span, "Internal server error during authentication",
                                                        code=5000,
                                                        error_code="AUTH_UNEXPECTED_ERROR", exception=e)

                # Mark the service as active with this user
                if not await state_manager.set_active(user_id, session_id):
                    logger.error(f"Failed to mark service as active for user {user_id}")
                    return await self._close_with_error(ws, span, "Service unable to handle session", code=5000,
                                                        error_code="SERVICE_STATE_ERROR")

                client_id = request.query.get('clientId', f"client-{time.time_ns()}")
                span.set_attribute("client_id", client_id)
                span.set_attribute("session_id", session_id)
                span.set_attribute("user_id", str(user_id))
                span.set_attribute("device_id", device_id)

                # Store client info directly on the websocket object
                ws._client_info = {
                    'session_id': session_id,
                    'user_id': user_id,
                    'client_id': client_id,
                    'device_id': device_id,
                    'connected_at': time.time(),
                    'last_activity': time.time()
                }

                # Add to active connections
                self._active_connections.append(ws)
                track_websocket_connection_count(len(self._active_connections))

                # Update session metadata
                try:
                    await self.session_manager.update_session_metadata(session_id, {
                        'device_id': device_id,  # Update device ID on new connection potentially
                        'frontend_connections': len(self._active_connections),
                        'last_ws_connection': time.time()
                    })
                except Exception as e:
                    logger.error(f"Failed to update session metadata during registration: {e}", exc_info=True)

                await connection_emitter.send_connected(ws, client_id=client_id, device_id=device_id,
                                                        session_id=session_id)

                # Publish event about new connection
                await event_bus.publish('ws_connection_established',
                                        session_id=session_id,
                                        client_id=client_id,
                                        user_id=user_id)

                try:
                    async for msg in ws:
                        if msg.type == WSMsgType.TEXT:
                            # Update last activity time
                            ws._client_info['last_activity'] = time.time()

                            # Also update session activity
                            await self.session_manager.update_session_activity(session_id)

                            # Dispatch the message
                            await self.dispatcher.dispatch_message(ws, session_id, user_id, client_id, msg.data)
                        elif msg.type == WSMsgType.ERROR:
                            logger.error(f"WS error: client={client_id}: {ws.exception()}")
                            track_websocket_error("AIOHTTP_CONNECTION_ERROR")
                            break
                        elif msg.type in (WSMsgType.CLOSING, WSMsgType.CLOSED):
                            logger.info(f"WS closing/closed by client: client={client_id}")
                            break
                except asyncio.CancelledError:
                    logger.info(f"WS message loop cancelled: client={client_id}")
                    raise
                except Exception as e:
                    logger.error(f"Error processing WS messages: client={client_id}: {e}",
                                 exc_info=True)
                    await error_emitter.send_error(ws=ws, error_code="MESSAGE_PROCESSING_ERROR",
                                                   message="Internal server error during message processing.",
                                                   span=span,
                                                   exception=e)
                finally:
                    logger.debug(f"Entering finally block for WS: client={client_id}")
                    if ws in self._active_connections:
                        self._active_connections.remove(ws)
                        track_websocket_connection_count(len(self._active_connections))

                        # Update session metadata with reduced connection count
                        try:
                            await self.session_manager.update_session_metadata(session_id, {
                                'frontend_connections': len(self._active_connections),
                                'last_ws_disconnection': time.time()
                            })
                        except Exception as e:
                            logger.error(f"Failed to update session metadata during disconnect: {e}", exc_info=True)

                    # Publish event about client disconnection
                    await event_bus.publish(
                        'ws_connection_closed',
                        session_id=session_id,
                        client_id=client_id,
                        session_empty=len(self._active_connections) == 0
                    )

                    # Reset service to ready state if this was the last connection
                    if len(self._active_connections) == 0:
                        logger.info("Last connection closed, resetting service to ready state")
                        await state_manager.reset_to_ready()

                logger.info(f"WS connection handler finished: client={client_id}")
                return ws

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

    async def broadcast_to_all(self, message: Any):
        """Broadcast a message to all connected clients"""
        connections_to_send = [ws for ws in self._active_connections if not ws.closed]
        if not connections_to_send:
            return

        if isinstance(message, dict):
            data = json.dumps(message)
            message_type = message.get('type', 'unknown')
        else:
            data = str(message)
            message_type = 'raw_string'

        logger.debug(f"Broadcasting '{message_type}' to {len(connections_to_send)} clients")

        tasks = [self._send_to_websocket(ws, data) for ws in connections_to_send]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                ws_error = connections_to_send[i]
                client_id = getattr(ws_error, '_client_info', {}).get('client_id', 'unknown')
                logger.error(f"Error broadcasting to client {client_id}: {result}")

    async def _send_to_websocket(self, ws: web.WebSocketResponse, data: str) -> None:
        """Send data to a websocket with error handling"""
        try:
            if not ws.closed:
                await ws.send_str(data)
        except ConnectionResetError:
            logger.warning(f"Connection reset sending to client.")
        except Exception as e:
            client_id = getattr(ws, '_client_info', {}).get('client_id', 'unknown')
            logger.error(f"Failed to send message to client {client_id}: {e}")
            raise

    # --- Event handlers ---

    async def handle_exchange_data(self, session_id: str, data: Dict[str, Any]):
        """Handle exchange data event by broadcasting to all clients"""
        await self.broadcast_to_all({
            'type': 'exchange_data',
            'data': data
        })

    async def handle_stream_error(self, session_id: str, error: str, **kwargs):
        """Handle stream error event by notifying clients"""
        await self.broadcast_to_all({
            'type': 'stream_error',
            'error': error
        })

    async def handle_simulator_ready(self, session_id: str, endpoint: str):
        """Handle simulator ready event by notifying clients"""
        await self.broadcast_to_all({
            'type': 'simulator_status',
            'status': 'RUNNING',
            'endpoint': endpoint
        })

    async def handle_simulator_stopped(self, session_id: str, simulator_id: str):
        """Handle simulator stopped event by notifying clients"""
        await self.broadcast_to_all({
            'type': 'simulator_status',
            'status': 'STOPPED',
            'simulator_id': simulator_id
        })

    async def handle_connection_quality_update(self, session_id: str, quality: str, reconnect_recommended: bool):
        """Handle connection quality update by notifying clients"""
        await self.broadcast_to_all({
            'type': 'connection_quality',
            'quality': quality,
            'reconnect_recommended': reconnect_recommended
        })

    async def close_all_connections(self, reason="Server shutting down"):
        """Gracefully close all WebSocket connections and publish shutdown event"""
        connection_count = len(self._active_connections)
        logger.info(f"Closing all ({connection_count}) WebSocket connections: {reason}")

        # Publish shutdown event
        await event_bus.publish('server_shutting_down', reason=reason)

        close_tasks = []
        for ws in self._active_connections:
            if not ws.closed:
                await connection_emitter.send_shutdown(ws, reason)
                close_tasks.append(ws.close(code=1001, message=reason.encode('utf-8')))

        await asyncio.gather(*close_tasks, return_exceptions=True)
        logger.info("Finished sending close() command to all websockets.")

        # Clear active connections
        self._active_connections.clear()
        track_websocket_connection_count(0)

        logger.info("All WebSocket connections closed and resources cleaned up.")

    async def _cleanup_stale_connections(self):
        """Periodically check for and clean up stale connections"""
        await asyncio.sleep(15)
        while True:
            try:
                await asyncio.sleep(config.websocket.heartbeat_interval)
                current_time = time.time()
                stale_connections = []
                timeout_threshold = (config.websocket.heartbeat_interval * 3) + 10

                for ws in self._active_connections:
                    if ws.closed:
                        stale_connections.append(ws)
                        continue
                        
                    info = getattr(ws, '_client_info', {})
                    last_activity = info.get('last_activity', info.get('connected_at', current_time))
                    inactive_time = current_time - last_activity

                    if inactive_time > timeout_threshold:
                        stale_connections.append(ws)
                        logger.warning(
                            f"Marking WS as stale: client={info.get('client_id')}, "
                            f"inactive for {inactive_time:.1f}s")

                if stale_connections:
                    logger.info(f"Cleaning up {len(stale_connections)} stale/closed WebSocket connections")

                    for ws in stale_connections:
                        if ws in self._active_connections:
                            self._active_connections.remove(ws)
                            
                        if not ws.closed:
                            # Send timeout message before closing
                            await connection_emitter.send_timeout(ws)
                            try:
                                await ws.close(code=1008, message=b'Policy violation - inactive')
                            except Exception as e:
                                logger.error(f"Error closing stale connection: {e}")
                    
                    # Update connection count metric
                    track_websocket_connection_count(len(self._active_connections))

            except asyncio.CancelledError:
                logger.info("Cleanup task cancelled.")
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}", exc_info=True)
                await asyncio.sleep(60)
