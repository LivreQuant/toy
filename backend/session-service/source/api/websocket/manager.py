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


# source/api/websocket/manager.py

class WebSocketManager:
    """Manages WebSocket connections for a single session."""

    def __init__(self, session_manager: SessionManager, stream_manager: StreamManager):
        """Initialize WebSocket manager."""
        self.session_manager = session_manager
        self.stream_manager = stream_manager

        # The session ID is now always taken from the session manager
        self.session_id = session_manager.session_id

        # Active connections list
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

        logger.info(f"WebSocketManager initialized for session {self.session_id}")

    async def handle_connection(self, request: web.Request) -> web.WebSocketResponse:
        """Handle incoming HTTP request, authentication, and message loop."""

        with optional_trace_span(self.tracer, "handle_websocket_connection") as span:
            # Check if service is ready for new connections
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

            try:
                # Authenticate user
                user_id, device_id = await self._authenticate_user(request, span)
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
            if not await state_manager.set_active(user_id, self.session_id):
                logger.error(f"Failed to mark service as active for user {user_id}")
                return await self._close_with_error(ws, span, "Service unable to handle session", code=5000,
                                                    error_code="SERVICE_STATE_ERROR")

            client_id = request.query.get('clientId', f"client-{time.time_ns()}")
            span.set_attribute("client_id", client_id)
            span.set_attribute("session_id", self.session_id)
            span.set_attribute("user_id", str(user_id))
            span.set_attribute("device_id", device_id)

            # Store client info directly on the websocket object
            ws._client_info = {
                'session_id': self.session_id,
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
                await self.session_manager.update_session_metadata({
                    'device_id': device_id,  # Update device ID on new connection potentially
                    'frontend_connections': len(self._active_connections),
                    'last_ws_connection': time.time()
                })
            except Exception as e:
                logger.error(f"Failed to update session metadata during registration: {e}", exc_info=True)

            await connection_emitter.send_connected(ws, client_id=client_id, device_id=device_id,
                                                    session_id=self.session_id)

            # Publish event about new connection
            await event_bus.publish('ws_connection_established',
                                    session_id=self.session_id,
                                    client_id=client_id,
                                    user_id=user_id)

            try:
                async for msg in ws:
                    if msg.type == WSMsgType.TEXT:
                        # Update last activity time
                        ws._client_info['last_activity'] = time.time()

                        # Also update session activity
                        await self.session_manager.update_session_activity()

                        # Dispatch the message
                        await self.dispatcher.dispatch_message(ws, user_id, client_id, msg.data)
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
                        await self.session_manager.update_session_metadata({
                            'frontend_connections': len(self._active_connections),
                            'last_ws_disconnection': time.time()
                        })
                    except Exception as e:
                        logger.error(f"Failed to update session metadata during disconnect: {e}", exc_info=True)

                # Publish event about client disconnection
                await event_bus.publish(
                    'ws_connection_closed',
                    session_id=self.session_id,
                    client_id=client_id,
                    session_empty=len(self._active_connections) == 0
                )

                # Reset service to ready state if this was the last connection
                if len(self._active_connections) == 0:
                    logger.info("Last connection closed, resetting service to ready state")
                    await state_manager.reset_to_ready()

            logger.info(f"WS connection handler finished: client={client_id}")
            return ws

    async def _authenticate_user(self, request, span) -> Tuple[str, str]:
        """Authenticate the WebSocket user"""
        query = request.query
        token = query.get('token')
        device_id = query.get('deviceId', 'default-device')

        # 1. Validate required parameters
        if not token:
            logger.warning("Authentication failed: Missing token query parameter")
            raise WebSocketClientError(
                message="Missing required parameter: token",
                error_code="MISSING_PARAMETERS"
            )

        # Validate token but don't enforce user matching
        validation_result = await validate_token_with_auth_service(token)

        if not validation_result.get('valid', False):
            logger.warning(f"Authentication failed: Invalid token for device {device_id}")
            raise AuthenticationError(
                message="Invalid authentication token",
            )

        user_id = validation_result.get('userId')

        if not user_id:
            logger.warning(f"Authentication failed: No user ID in token for device {device_id}")
            raise AuthenticationError(
                message="Invalid authentication token - missing user ID",
            )

        logger.info(f"User {user_id} authenticated with device {device_id}")
        return user_id, device_id
