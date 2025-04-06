"""
WebSocket connection manager.
Handles WebSocket connections, protocol, and broadcasting.
"""
import logging
import json
import time
import asyncio
from typing import Dict, Set, Any, Optional
from aiohttp import web, WSMsgType
from opentelemetry import trace

from source.utils.metrics import (
    track_websocket_connection_count, track_websocket_message,
    track_websocket_error, track_client_reconnection
)
from source.utils.tracing import optional_trace_span
from source.config import config
from source.api.websocket.protocol import WebSocketProtocol

logger = logging.getLogger('websocket_manager')

class WebSocketManager:
    """Manages WebSocket connections for sessions"""
    
    def __init__(self, session_manager, redis_client=None):
        """
        Initialize WebSocket manager
        
        Args:
            session_manager: Session manager instance
            redis_client: Optional Redis client for session coordination
        """
        self.session_manager = session_manager
        self.redis = redis_client
        self.connections = {}  # session_id -> set of ws connections
        self.connection_info = {}  # ws -> connection info
        self.protocol = WebSocketProtocol(session_manager)
        
        # Start cleanup task
        self.cleanup_task = asyncio.create_task(self._cleanup_stale_connections())

        # Initialize tracer
        self.tracer = trace.get_tracer("websocket_manager")

        # Track initial connection count
        track_websocket_connection_count(0)

    async def handle_connection(self, request):
        """WebSocket connection handler"""
        with optional_trace_span(self.tracer, "handle_websocket_connection") as span:

            # Initialize WebSocket
            ws = web.WebSocketResponse(
                heartbeat=config.websocket.heartbeat_interval,
                autoping=True
            )
            await ws.prepare(request)

            # Extract parameters
            query = request.query
            session_id = query.get('sessionId')
            token = query.get('token')

            span.set_attribute("session_id", session_id)
            span.set_attribute("has_token", token is not None)

            if not session_id or not token:
                error_msg = "Missing sessionId or token"
                span.set_attribute("error", error_msg)
                await ws.send_json({
                    'type': 'error',
                    'error': 'Missing sessionId or token'
                })
                await ws.close(code=1008, message=b'Missing parameters')
                track_websocket_error("missing_parameters")
                return ws

            # Validate session
            user_id = await self.session_manager.validate_session(session_id, token)

            span.set_attribute("user_id", user_id)
            span.set_attribute("session_valid", user_id is not None)

            if not user_id:
                error_msg = "Invalid session or token"
                span.set_attribute("error", error_msg)
                await ws.send_json({
                    'type': 'error',
                    'error': 'Invalid session or token'
                })
                await ws.close(code=1008, message=b'Invalid session')
                track_websocket_error("invalid_session")
                return ws

            # Register connection
            client_id = request.query.get('clientId', f"client-{time.time()}")
            span.set_attribute("client_id", client_id)

            await self._register_connection(ws, session_id, user_id, client_id)

            # Send connected message
            await ws.send_json({
                'type': 'connected',
                'sessionId': session_id,
                'clientId': client_id,
                'podName': config.kubernetes.pod_name,
                'timestamp': int(time.time() * 1000)
            })
            track_websocket_message("sent", "connected")

            # Process messages
            try:
                async for msg in ws:
                    if msg.type == WSMsgType.TEXT:
                        track_websocket_message("received", "text")
                        await self._process_message(ws, msg.data)
                    elif msg.type == WSMsgType.ERROR:
                        logger.error(f"WebSocket connection closed with error: {ws.exception()}")
                        span.record_exception(ws.exception())
                        track_websocket_error("connection_error")
                        break
            except Exception as e:
                logger.error(f"Error processing WebSocket messages: {e}")
                span.record_exception(e)
                track_websocket_error("processing_error")
            finally:
                # Unregister connection
                await self._unregister_connection(ws)

            return ws
    
    async def _register_connection(self, ws, session_id, user_id, client_id):
        """Register a new WebSocket connection"""
        # Add to connections dict
        with optional_trace_span(self.tracer, "register_websocket_connection") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("user_id", user_id)
            span.set_attribute("client_id", client_id)

            if session_id not in self.connections:
                self.connections[session_id] = set()

            self.connections[session_id].add(ws)

            # Store connection info
            self.connection_info[ws] = {
                'session_id': session_id,
                'user_id': user_id,
                'client_id': client_id,
                'connected_at': time.time(),
                'last_activity': time.time()
            }

            # Update session metadata
            connections_count = len(self.connections.get(session_id, set()))
            await self.session_manager.db_manager.update_session_metadata(session_id, {
                'frontend_connections': connections_count,
                'last_ws_connection': time.time()
            })

            # Update metrics
            total_connections = sum(len(conns) for conns in self.connections.values())
            track_websocket_connection_count(total_connections)

            # Update Redis if available
            if self.redis:
                await self.redis.set(
                    f"connection:{session_id}:ws_count",
                    connections_count,
                    ex=3600  # 1 hour expiry
                )

                # Publish connection event
                await self.redis.publish('session_events', json.dumps({
                    'type': 'client_connected',
                    'session_id': session_id,
                    'user_id': user_id,
                    'client_id': client_id,
                    'pod_name': config.kubernetes.pod_name,
                    'timestamp': time.time()
                }))

            logger.info(f"Registered WebSocket connection for session {session_id}, client {client_id}")

    async def _unregister_connection(self, ws):
        """Unregister a WebSocket connection"""
        # Get connection info
        conn_info = self.connection_info.pop(ws, None)
        
        if not conn_info:
            return
        
        session_id = conn_info['session_id']
        client_id = conn_info['client_id']
        user_id = conn_info['user_id']
        
        # Remove from connections dict
        if session_id in self.connections:
            self.connections[session_id].discard(ws)
            
            # Remove empty session
            if not self.connections[session_id]:
                del self.connections[session_id]
        
        # Update session metadata
        connections_count = len(self.connections.get(session_id, set()))
        await self.session_manager.db_manager.update_session_metadata(session_id, {
            'frontend_connections': connections_count,
            'last_ws_disconnection': time.time()
        })
        
        # Update Redis if available
        if self.redis:
            await self.redis.set(
                f"connection:{session_id}:ws_count", 
                connections_count,
                ex=3600  # 1 hour expiry
            )
            
            # Publish disconnection event
            await self.redis.publish('session_events', json.dumps({
                'type': 'client_disconnected',
                'session_id': session_id,
                'user_id': user_id,
                'client_id': client_id,
                'pod_name': config.kubernetes.pod_name,
                'timestamp': time.time()
            }))
        
        logger.info(f"Unregistered WebSocket connection for session {session_id}, client {client_id}")
    
    async def _process_message(self, ws, message_data):
        """Process an incoming WebSocket message"""
        # Get connection info
        conn_info = self.connection_info.get(ws)
        if not conn_info:
            logger.warning("Received message from unknown connection")
            return
        
        # Update last activity time
        conn_info['last_activity'] = time.time()
        
        # Forward to protocol handler
        await self.protocol.process_message(
            ws, 
            conn_info['session_id'], 
            conn_info['user_id'], 
            conn_info['client_id'],
            message_data
        )
    
    async def broadcast_to_session(self, session_id, message):
        """
        Broadcast a message to all connections for a session
        
        Args:
            session_id: Session ID to broadcast to
            message: Message to broadcast (dict or string)
        """
        if session_id not in self.connections:
            return
        
        # Prepare message
        if isinstance(message, dict):
            data = json.dumps(message)
        else:
            data = message
        
        # Send to all connections
        for ws in list(self.connections.get(session_id, set())):
            try:
                if not ws.closed:
                    await ws.send_str(data)
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket: {e}")
    
    async def close_all_connections(self, reason="Server shutting down"):
        """
        Close all active WebSocket connections
        
        Args:
            reason: Reason for closure
        """
        # Send close message to all connections
        for session_id, connections in list(self.connections.items()):
            for ws in list(connections):
                try:
                    if not ws.closed:
                        await ws.send_json({
                            'type': 'server_shutdown',
                            'reason': reason
                        })
                        await ws.close(code=1001, message=reason.encode())
                except Exception as e:
                    logger.error(f"Error closing WebSocket: {e}")
        
        # Clear connection tracking
        self.connections.clear()
        self.connection_info.clear()
        
        # Cancel cleanup task
        if hasattr(self, 'cleanup_task'):
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
    
    async def _cleanup_stale_connections(self):
        """Periodically clean up stale connections"""
        while True:
            try:
                # Sleep first to avoid immediate cleanup
                await asyncio.sleep(60)  # Check every minute
                
                # Find stale connections
                current_time = time.time()
                stale_connections = []
                
                for ws, info in list(self.connection_info.items()):
                    # Check last activity time (3x heartbeat interval)
                    inactivity = current_time - info.get('last_activity', 0)
                    max_inactivity = config.websocket.heartbeat_interval * 3
                    
                    if inactivity > max_inactivity:
                        stale_connections.append(ws)
                
                # Close stale connections
                for ws in stale_connections:
                    if not ws.closed:
                        try:
                            await ws.send_json({
                                'type': 'timeout',
                                'error': 'Connection timeout due to inactivity'
                            })
                            await ws.close(code=1001, message=b'Connection timeout')
                        except Exception as e:
                            logger.error(f"Error closing stale connection: {e}")
                    
                    # Make sure it's unregistered
                    await self._unregister_connection(ws)
                
                if stale_connections:
                    logger.info(f"Cleaned up {len(stale_connections)} stale WebSocket connections")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in WebSocket cleanup task: {e}")