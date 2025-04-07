# source/api/websocket/manager.py
"""
WebSocket connection manager.
Handles WebSocket connections, authentication, and message routing.
"""
import asyncio
import json
import logging
import time
from typing import Dict, Set, Any, Optional

from aiohttp import web, WSMsgType
from opentelemetry import trace

from source.utils.metrics import (
    track_websocket_connection_count,
    track_websocket_message,
    track_websocket_error
)
from source.utils.tracing import optional_trace_span
from source.config import config
from source.api.websocket.protocol import WebSocketProtocol

logger = logging.getLogger('websocket_manager')


class WebSocketManager:
    """Manages WebSocket connections and message routing"""

    def __init__(self, session_manager, redis_client=None):
        """
        Initialize WebSocket manager

        Args:
            session_manager: The session manager
            redis_client: Optional Redis client for cross-node communication
        """
        self.session_manager = session_manager
        self.redis_client = redis_client

        # Track connections
        self.connections = {}  # session_id -> set of ws connections
        self.connection_info = {}  # ws -> connection info

        # Initialize protocol handler
        self.protocol = WebSocketProtocol(session_manager, self)

        # Start cleanup task
        self.cleanup_task = asyncio.create_task(self._cleanup_stale_connections())

        # Initialize tracer
        self.tracer = trace.get_tracer("websocket_manager")

        # Track initial connection count
        track_websocket_connection_count(0)

    async def handle_connection(self, request):
        """
        Handle WebSocket connection

        Args:
            request: The HTTP request

        Returns:
            WebSocket response
        """
        with optional_trace_span(self.tracer, "handle_websocket_connection") as span:
            # Initialize WebSocket
            ws = web.WebSocketResponse(
                heartbeat=config.websocket.heartbeat_interval,
                autoping=True
            )
            await ws.prepare(request)

            # Extract query parameters
            query = request.query
            token = query.get('token')
            device_id = query.get('deviceId')
            session_id = query.get('sessionId')

            span.set_attribute("device_id", device_id)

            # Validate parameters
            if not token or not device_id:
                error_msg = "Missing required parameters: token or deviceId"
                span.set_attribute("error", error_msg)
                await ws.send_json({
                    'type': 'error',
                    'message': error_msg
                })
                await ws.close(code=4001)
                track_websocket_error("missing_parameters")
                return ws

            # Validate token and get user ID if session ID is present
            user_id = None
            if session_id:
                user_id = await self.session_manager.validate_session(session_id, token, device_id)
                if not user_id:
                    # Session is invalid, try to get user ID from token
                    user_id = await self.session_manager.get_user_from_token(token)
            else:
                # No session ID, get user ID from token
                user_id = await self.session_manager.get_user_from_token(token)

            span.set_attribute("user_id", user_id)

            # Check if we have a valid user
            if not user_id:
                error_msg = "Invalid authentication token"
                span.set_attribute("error", error_msg)
                await ws.send_json({
                    'type': 'error',
                    'message': error_msg
                })
                await ws.close(code=4001)
                track_websocket_error("invalid_token")
                return ws

            # Get or create session
            if not session_id:
                # Create new session
                client_ip = request.remote
                session_id, is_new = await self.session_manager.create_session(user_id, device_id, token, client_ip)
                if not session_id:
                    error_msg = "Failed to create session"
                    span.set_attribute("error", error_msg)
                    await ws.send_json({
                        'type': 'error',
                        'message': error_msg
                    })
                    await ws.close(code=4001)
                    track_websocket_error("session_creation_failed")
                    return ws

            span.set_attribute("session_id", session_id)

            # Generate client ID if not provided
            client_id = query.get('clientId', f"client-{time.time()}")
            span.set_attribute("client_id", client_id)

            # Register connection
            await self._register_connection(ws, session_id, user_id, client_id, device_id)

            # Send connected message
            await ws.send_json({
                'type': 'connected',
                'clientId': client_id,
                'deviceId': device_id,
                'podName': config.kubernetes.pod_name,
                'timestamp': int(time.time() * 1000)
            })
            track_websocket_message("sent", "connected")

            # Process messages
            try:
                async for msg in ws:
                    if msg.type == WSMsgType.TEXT:
                        await self.protocol.process_message(ws, session_id, user_id, client_id, msg.data)
                    elif msg.type == WSMsgType.ERROR:
                        logger.error(f"WebSocket error: {ws.exception()}")
                        track_websocket_error("connection_error")
            except Exception as e:
                logger.error(f"Error processing WebSocket messages: {e}", exc_info=True)
                track_websocket_error("processing_error")
            finally:
                # Unregister connection
                await self._unregister_connection(ws)

            return ws

    async def _register_connection(self, ws, session_id, user_id, client_id, device_id):
        """
        Register a WebSocket connection

        Args:
            ws: The WebSocket connection
            session_id: Session ID
            user_id: User ID
            client_id: Client ID
            device_id: Device ID
        """
        # Initialize connections set if needed
        if session_id not in self.connections:
            self.connections[session_id] = set()

        # Add connection
        self.connections[session_id].add(ws)

        # Store connection info
        self.connection_info[ws] = {
            'session_id': session_id,
            'user_id': user_id,
            'client_id': client_id,
            'device_id': device_id,
            'connected_at': time.time(),
            'last_activity': time.time()
        }

        # Update session metadata
        await self.session_manager.db_manager.update_session_metadata(session_id, {
            'device_id': device_id,
            'frontend_connections': len(self.connections.get(session_id, set())),
            'last_ws_connection': time.time()
        })

        # Update metrics
        total_connections = sum(len(conns) for conns in self.connections.values())
        track_websocket_connection_count(total_connections)

        logger.info(f"WebSocket connection registered: session={session_id}, client={client_id}, device={device_id}")

    async def _unregister_connection(self, ws):
        """
        Unregister a WebSocket connection

        Args:
            ws: The WebSocket connection
        """
        # Get connection info
        conn_info = self.connection_info.pop(ws, None)
        if not conn_info:
            return

        session_id = conn_info['session_id']

        # Remove from connections
        if session_id in self.connections:
            self.connections[session_id].discard(ws)

            # If no more connections for this session, remove the set
            if not self.connections[session_id]:
                await self.protocol.stop_exchange_data_stream(session_id)
                del self.connections[session_id]

        # Update session metadata
        await self.session_manager.db_manager.update_session_metadata(session_id, {
            'frontend_connections': len(self.connections.get(session_id, set()) or set()),
            'last_ws_disconnection': time.time()
        })

        # Update metrics
        total_connections = sum(len(conns) for conns in self.connections.values())
        track_websocket_connection_count(total_connections)

        logger.info(f"WebSocket connection unregistered: session={session_id}, client={conn_info['client_id']}")

    async def broadcast_to_session(self, session_id, message):
        """
        Broadcast a message to all connections for a session

        Args:
            session_id: The session ID
            message: The message to broadcast
        """
        if session_id not in self.connections:
            return

        # Convert to string if it's a dict
        if isinstance(message, dict):
            data = json.dumps(message)
        else:
            data = message

        # Broadcast to all connections
        for ws in list(self.connections.get(session_id, set())):
            try:
                if not ws.closed:
                    await ws.send_str(data)
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")

    async def close_all_connections(self, reason="Server shutting down"):
        """
        Close all WebSocket connections

        Args:
            reason: The reason for closing
        """
        logger.info(f"Closing all WebSocket connections: {reason}")

        # Close all connections
        for session_id, connections in list(self.connections.items()):
            for ws in list(connections):
                try:
                    if not ws.closed:
                        await ws.send_json({
                            'type': 'shutdown',
                            'message': reason
                        })
                        await ws.close()
                except Exception as e:
                    logger.error(f"Error closing WebSocket connection: {e}")

        # Clear connections
        self.connections.clear()
        self.connection_info.clear()

        # Cancel cleanup task
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

        # Update metrics
        track_websocket_connection_count(0)

    async def _cleanup_stale_connections(self):
        """Periodically clean up stale connections"""
        try:
            while True:
                # Wait for a while
                await asyncio.sleep(60)

                # Find stale connections
                current_time = time.time()
                stale_connections = []

                for ws, info in list(self.connection_info.items()):
                    # Get last activity time
                    last_activity = info.get('last_activity', 0)

                    # Calculate inactivity time
                    inactive_time = current_time - last_activity

                    # Check if inactive for too long (3x heartbeat interval)
                    if inactive_time > config.websocket.heartbeat_interval * 3:
                        stale_connections.append(ws)

                # Close stale connections
                if stale_connections:
                    logger.info(f"Cleaning up {len(stale_connections)} stale WebSocket connections")

                    for ws in stale_connections:
                        if not ws.closed:
                            try:
                                await ws.send_json({
                                    'type': 'timeout',
                                    'message': 'Connection timed out due to inactivity'
                                })
                                await ws.close()
                            except Exception as e:
                                logger.error(f"Error closing stale connection: {e}")

                        # Unregister connection
                        await self._unregister_connection(ws)

        except asyncio.CancelledError:
            logger.info("WebSocket cleanup task cancelled")
        except Exception as e:
            logger.error(f"Error in WebSocket cleanup task: {e}", exc_info=True)