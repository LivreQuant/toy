# session-manager-service/source/websocket/handler.py

import json
import logging
import time
import asyncio
import jwt
from aiohttp import web, WSMsgType

logger = logging.getLogger('websocket_handler')

class WebSocketHandler:
    def __init__(self, session_manager, auth_client, redis_client):
        self.session_manager = session_manager
        self.auth_client = auth_client
        self.redis = redis_client
        self.connections = {}  # {session_id: set(websockets)}
        self.connection_info = {}  # {websocket: {session_id, user_id, last_heartbeat}}
        
        # Heartbeat settings
        self.heartbeat_interval = 15  # seconds
        self.heartbeat_timeout = 45  # seconds (3 missed heartbeats)
        
        # Start background tasks
        self.cleanup_task = asyncio.create_task(self._cleanup_connections())
    
    async def websocket_handler(self, request):
        """Handle WebSocket connections"""
        ws = web.WebSocketResponse(heartbeat=self.heartbeat_interval)
        await ws.prepare(request)
        
        # Extract parameters from query string
        query = request.query
        session_id = query.get('sessionId')
        token = query.get('token')
        
        if not session_id or not token:
            await ws.send_json({
                'type': 'error',
                'error': 'Missing sessionId or token'
            })
            await ws.close(code=1008, message=b'Missing sessionId or token')
            return ws
        
        # Validate token
        try:
            # Verify JWT token with auth service
            validate_result = await self.auth_client.validate_token(token)
            if not validate_result.get('valid'):
                await ws.send_json({
                    'type': 'error',
                    'error': 'Invalid authentication token'
                })
                await ws.close(code=1008, message=b'Invalid authentication token')
                return ws
            
            user_id = validate_result.get('user_id')
            
            # Validate session
            session = await self.session_manager.get_session(session_id)
            if not session:
                await ws.send_json({
                    'type': 'error',
                    'error': 'Invalid session'
                })
                await ws.close(code=1008, message=b'Invalid session')
                return ws
            
            # Check if session belongs to user
            if str(session.get('user_id')) != str(user_id):
                await ws.send_json({
                    'type': 'error',
                    'error': 'Session does not belong to this user'
                })
                await ws.close(code=1008, message=b'Unauthorized')
                return ws
            
            # Register connection
            if session_id not in self.connections:
                self.connections[session_id] = set()
            
            self.connections[session_id].add(ws)
            self.connection_info[ws] = {
                'session_id': session_id,
                'user_id': user_id,
                'last_heartbeat': time.time(),
                'connected_at': time.time()
            }
            
            # Update session activity
            await self.session_manager.db.update_session_activity(session_id)
            
            # Update Redis
            self.redis.set(
                f'connection:{session_id}:ws_count',
                len(self.connections.get(session_id, set())),
                ex=3600
            )
            
            self.redis.set(
                f'connection:{session_id}:last_active',
                time.time(),
                ex=3600
            )
            
            # Update session metadata for connection count
            await self.session_manager.db.update_session_metadata(session_id, {
                'frontend_connections': len(self.connections.get(session_id, set())),
                'last_ws_connection': time.time()
            })
            
            # Send connection acknowledgement
            await ws.send_json({
                'type': 'connected',
                'sessionId': session_id,
                'userId': user_id,
                'podName': self.session_manager.pod_name,
                'timestamp': int(time.time() * 1000)
            })
            
            # Broadcast connection event to all pods
            self.redis.publish('session_events', json.dumps({
                'type': 'client_connected',
                'session_id': session_id,
                'user_id': user_id,
                'pod_name': self.session_manager.pod_name,
                'timestamp': time.time()
            }))
            
            logger.info(f"WebSocket connection established for session {session_id}")
            
            # Process incoming messages
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self._handle_message(ws, msg.data)
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket connection closed with error: {ws.exception()}")
                    break
            
            # Handle connection close
            await self._remove_connection(ws)
            return ws
            
        except Exception as e:
            logger.error(f"Error in WebSocket handler: {e}")
            await ws.send_json({
                'type': 'error',
                'error': 'Internal server error'
            })
            await ws.close(code=1011, message=b'Internal server error')
            return ws
    
    async def _handle_message(self, ws, data):
        """Handle incoming WebSocket messages"""
        # Get connection info
        conn_info = self.connection_info.get(ws)
        if not conn_info:
            logger.warning("Received message from unknown connection")
            return
        
        session_id = conn_info['session_id']
        user_id = conn_info['user_id']
        
        try:
            # Parse message
            message = json.loads(data)
            message_type = message.get('type')
            
            # Update last heartbeat timestamp
            conn_info['last_heartbeat'] = time.time()
            
            # Handle message based on type
            if message_type == 'heartbeat' or message_type == 'ping':
                # Handle heartbeat/ping
                await self._handle_heartbeat(ws, message)
                
                # Update session activity in DB
                await self.session_manager.db.update_session_activity(session_id)
                
                # Update Redis
                self.redis.set(
                    f'connection:{session_id}:last_active',
                    time.time(),
                    ex=3600
                )
            
            elif message_type == 'connection_quality':
                # Handle connection quality report
                await self._handle_connection_quality(ws, message)
                
            elif message_type == 'subscribe':
                # Handle data subscription
                symbols = message.get('symbols', [])
                await self._handle_subscription(ws, session_id, user_id, symbols)
                
            elif message_type == 'reconnect':
                # Handle explicit reconnect request
                await self._handle_reconnect_request(ws, message)
                
            else:
                logger.warning(f"Unknown message type: {message_type}")
                await ws.send_json({
                    'type': 'error',
                    'error': f'Unknown message type: {message_type}'
                })
        
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON message: {data}")
            await ws.send_json({
                'type': 'error',
                'error': 'Invalid JSON message'
            })
        
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            await ws.send_json({
                'type': 'error',
                'error': f'Server error: {str(e)}'
            })
    
    async def _handle_heartbeat(self, ws, message):
        """Handle heartbeat message"""
        # Get client timestamp if available
        client_timestamp = message.get('timestamp', 0)
        
        # Calculate latency if client timestamp is provided
        latency = None
        if client_timestamp:
            latency = int(time.time() * 1000) - client_timestamp
        
        # Send heartbeat response
        await ws.send_json({
            'type': 'heartbeat_ack',
            'timestamp': int(time.time() * 1000),
            'clientTimestamp': client_timestamp,
            'latency': latency
        })
        
        # Update connection info
        conn_info = self.connection_info.get(ws)
        if conn_info:
            conn_info['last_heartbeat'] = time.time()
            conn_info['latency'] = latency
    
    async def _handle_connection_quality(self, ws, message):
        """Handle connection quality report"""
        conn_info = self.connection_info.get(ws)
        if not conn_info:
            return
        
        session_id = conn_info['session_id']
        token = message.get('token')
        
        if not token:
            await ws.send_json({
                'type': 'error',
                'error': 'Missing token in connection quality report'
            })
            return
        
        # Build connection quality data
        data = {
            'latency_ms': message.get('latencyMs', 0),
            'missed_heartbeats': message.get('missedHeartbeats', 0),
            'connection_type': message.get('connectionType', 'websocket')
        }
        
        # Update connection quality in session manager
        quality, reconnect_recommended = await self.session_manager.update_connection_quality(
            session_id, token, data)
        
        # Store metrics in Redis
        self.redis.hmset(
            f'connection:{session_id}:metrics',
            {
                'quality': quality,
                'latency_ms': data['latency_ms'],
                'missed_heartbeats': data['missed_heartbeats'],
                'connection_type': data['connection_type'],
                'timestamp': time.time()
            }
        )
        self.redis.expire(f'connection:{session_id}:metrics', 3600)
        
        # Send response
        await ws.send_json({
            'type': 'connection_quality_update',
            'quality': quality,
            'reconnectRecommended': reconnect_recommended
        })
    
    async def _handle_subscription(self, ws, session_id, user_id, symbols):
        """Handle subscription to data feeds"""
        # Store subscription in session metadata
        await self.session_manager.db.update_session_metadata(session_id, {
            'subscriptions': {
                'market_data': {
                    'symbols': symbols,
                    'timestamp': time.time()
                }
            }
        })
        
        # Store in Redis for quick lookup
        self.redis.set(
            f'subscription:{session_id}:symbols',
            json.dumps(symbols),
            ex=3600
        )
        
        # Acknowledge subscription
        await ws.send_json({
            'type': 'subscription_ack',
            'symbols': symbols
        })
    
    async def _handle_reconnect_request(self, ws, message):
        """Handle explicit reconnect request"""
        conn_info = self.connection_info.get(ws)
        if not conn_info:
            return
        
        session_id = conn_info['session_id']
        token = message.get('token')
        attempt = message.get('attempt', 1)
        
        if not token:
            await ws.send_json({
                'type': 'error',
                'error': 'Missing token in reconnect request'
            })
            return
        
        # Perform reconnection via session manager
        result, error = await self.session_manager.reconnect_session(
            session_id, token, attempt)
        
        if not result:
            await ws.send_json({
                'type': 'error',
                'error': error
            })
            return
        
        # Send reconnection result
        await ws.send_json({
            'type': 'reconnect_result',
            'success': True,
            'sessionId': result['session_id'],
            'simulatorId': result.get('simulator_id'),
            'simulatorStatus': result.get('simulator_status', 'UNKNOWN'),
            'podTransferred': result.get('pod_transferred', False),
            'newSession': result.get('new_session', False)
        })
    
    async def _remove_connection(self, ws):
        """Remove WebSocket connection when closed"""
        conn_info = self.connection_info.pop(ws, None)
        if not conn_info:
            return
        
        session_id = conn_info['session_id']
        
        if session_id in self.connections:
            self.connections[session_id].discard(ws)
            
            # Remove session set if empty
            if not self.connections[session_id]:
                del self.connections[session_id]
            
            # Update Redis
            conn_count = len(self.connections.get(session_id, set()))
            self.redis.set(
                f'connection:{session_id}:ws_count',
                conn_count,
                ex=3600
            )
            
            # Update session metadata
            await self.session_manager.db.update_session_metadata(session_id, {
                'frontend_connections': conn_count
            })
            
            # Broadcast disconnect event to all pods
            self.redis.publish('session_events', json.dumps({
                'type': 'client_disconnected',
                'session_id': session_id,
                'pod_name': self.session_manager.pod_name,
                'timestamp': time.time()
            }))
            
            logger.info(f"WebSocket connection closed for session {session_id}")
    
    async def _cleanup_connections(self):
        """Background task to clean up stale connections"""
        while True:
            try:
                # Sleep first to avoid immediate cleanup
                await asyncio.sleep(30)  # Check every 30 seconds
                
                now = time.time()
                to_close = []
                
                # Find stale connections
                for ws, info in self.connection_info.items():
                    last_heartbeat = info.get('last_heartbeat', 0)
                    if now - last_heartbeat > self.heartbeat_timeout:
                        logger.warning(f"Connection timeout for session {info.get('session_id')}")
                        to_close.append(ws)
                
                # Close stale connections
                for ws in to_close:
                    if not ws.closed:
                        await ws.send_json({
                            'type': 'error',
                            'error': 'Connection timeout'
                        })
                        await ws.close(code=1001, message=b'Connection timeout')
                    
                    # In case the close doesn't trigger _remove_connection
                    await self._remove_connection(ws)
            
            except asyncio.CancelledError:
                # Task was cancelled, exit cleanly
                break
            
            except Exception as e:
                logger.error(f"Error in connection cleanup: {e}")
    
    async def broadcast_to_session(self, session_id, message):
        """Broadcast a message to all connections for a session"""
        if session_id not in self.connections:
            return
        
        # Convert dict to JSON if needed
        if isinstance(message, dict):
            data = json.dumps(message)
        else:
            data = message
        
        # Get all connections for this session
        connections = list(self.connections.get(session_id, set()))
        
        for ws in connections:
            try:
                if not ws.closed:
                    await ws.send_str(data)
            except Exception as e:
                logger.error(f"Error sending broadcast to WebSocket: {e}")
    
    async def close_all_connections(self, reason="Server shutting down"):
        """Close all active WebSocket connections"""
        for session_id, connections in list(self.connections.items()):
            for ws in list(connections):
                try:
                    if not ws.closed:
                        await ws.send_json({
                            'type': 'server_shutdown',
                            'reason': reason
                        })
                        await ws.close(code=1001, message=f"Server shutting down: {reason}".encode())
                except Exception as e:
                    logger.error(f"Error closing WebSocket: {e}")
            
            # Clear connections for this session
            self.connections[session_id] = set()
        
        # Clear all connections
        self.connections = {}
        self.connection_info = {}
    
    async def shutdown(self):
        """Clean shutdown of the WebSocket handler"""
        # Cancel cleanup task
        if hasattr(self, 'cleanup_task'):
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        await self.close_all_connections("Server shutting down")