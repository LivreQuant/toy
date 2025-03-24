# interface/session-manager-service/source/websocket/manager.py

import logging
import json
import asyncio
import time
from typing import Dict, Set, Optional, Any, Callable, List, Tuple
from aiohttp import web, WSMsgType

from ..utils.backoff_strategy import BackoffStrategy
from ..utils.circuit_breaker import CircuitBreaker, CircuitOpenError

logger = logging.getLogger('websocket_manager')

class WebSocketManager:
    """Manages WebSocket connections for session maintenance"""
    
    def __init__(self, session_manager):
        self.session_manager = session_manager
        self.connections = {}  # session_id -> set of WebSocket connections
        self.heartbeat_interval = 10  # seconds
        
        # Create circuit breakers for various service connections
        self.circuit_breakers = {
            'session_api': CircuitBreaker('session_api', failure_threshold=5, reset_timeout_ms=60000),
            'auth_api': CircuitBreaker('auth_api', failure_threshold=5, reset_timeout_ms=60000),
            'simulator_api': CircuitBreaker('simulator_api', failure_threshold=5, reset_timeout_ms=60000)
        }
        
        # Create backoff strategy for reconnections
        self.backoff_strategy = BackoffStrategy(
            initial_backoff_ms=1000,
            max_backoff_ms=30000,
            jitter_factor=0.5
        )
    
    async def websocket_handler(self, request):
        """Handle new WebSocket connections"""
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
            await ws.close()
            return ws
        
        # Validate session
        try:
            # Use circuit breaker to protect against cascading failures
            user_id = await self.circuit_breakers['session_api'].execute(
                self.session_manager.validate_session, session_id, token
            )
            
            if not user_id:
                await ws.send_json({
                    'type': 'error',
                    'error': 'Invalid session or token'
                })
                await ws.close()
                return ws
                
        except CircuitOpenError as e:
            # Circuit is open, fast-fail the connection
            await ws.send_json({
                'type': 'error',
                'error': f'Service temporarily unavailable: {str(e)}',
                'retry_after_ms': e.remaining_ms
            })
            await ws.close()
            return ws
        except Exception as e:
            logger.error(f"Error validating session: {e}")
            await ws.send_json({
                'type': 'error',
                'error': 'Error validating session'
            })
            await ws.close()
            return ws
        
        # Register this connection
        if session_id not in self.connections:
            self.connections[session_id] = set()
        
        # Add connection
        self.connections[session_id].add(ws)
        
        # Send connection acknowledgement
        await ws.send_json({
            'type': 'connected',
            'sessionId': session_id,
            'userId': user_id,
            'podName': self.session_manager.pod_name
        })
        
        # Log session connection
        logger.info(f"WebSocket connection established for session {session_id}")
        
        # Update session metadata
        try:
            session = await self.session_manager.get_session(session_id)
            frontend_connections = session.get('frontend_connections', 0)
            
            await self.session_manager.db.update_session_metadata(session_id, {
                'frontend_connections': frontend_connections + 1
            })
        except Exception as e:
            logger.error(f"Error updating session metadata: {e}")
        
        # Process incoming messages
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self.handle_message(ws, session_id, user_id, msg.data)
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket connection closed with error: {ws.exception()}")
                    break
        finally:
            # Unregister connection
            if session_id in self.connections and ws in self.connections[session_id]:
                self.connections[session_id].remove(ws)
                
                # If no more connections, remove entry
                if not self.connections[session_id]:
                    del self.connections[session_id]
                
                # Update session metadata
                try:
                    session = await self.session_manager.get_session(session_id)
                    if session:
                        frontend_connections = max(0, session.get('frontend_connections', 1) - 1)
                        await self.session_manager.db.update_session_metadata(session_id, {
                            'frontend_connections': frontend_connections
                        })
                except Exception as e:
                    logger.error(f"Error updating session metadata: {e}")
                
                logger.info(f"WebSocket connection closed for session {session_id}")
        
        return ws
    
    async def handle_message(self, ws, session_id, user_id, data):
        """Handle incoming WebSocket messages"""
        try:
            message = json.loads(data)
            message_type = message.get('type')
            
            if message_type == 'heartbeat':
                # Process heartbeat
                await self.handle_heartbeat(ws, session_id, message)
            elif message_type == 'connection_quality':
                # Process connection quality update
                await self.handle_connection_quality(ws, session_id, message)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                await ws.send_json({
                    'type': 'error',
                    'error': f'Unknown message type: {message_type}'
                })
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON: {data}")
            await ws.send_json({
                'type': 'error',
                'error': 'Invalid JSON message'
            })
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await ws.send_json({
                'type': 'error',
                'error': f'Server error: {str(e)}'
            })
    
    async def handle_heartbeat(self, ws, session_id, message):
        """Handle client heartbeat message"""
        try:
            # Update session activity
            await self.circuit_breakers['session_api'].execute(
                self.session_manager.db.update_session_activity, session_id
            )
            
            # Send heartbeat response
            await ws.send_json({
                'type': 'heartbeat_ack',
                'timestamp': int(time.time() * 1000),
                'clientTimestamp': message.get('timestamp', 0)
            })
        except CircuitOpenError as e:
            # Circuit is open, but we can still respond to the client
            # Just don't update the database
            await ws.send_json({
                'type': 'heartbeat_ack',
                'timestamp': int(time.time() * 1000),
                'clientTimestamp': message.get('timestamp', 0),
                'warning': 'Database connectivity issues, some features may be limited'
            })
        except Exception as e:
            logger.error(f"Error handling heartbeat: {e}")
            await ws.send_json({
                'type': 'error',
                'error': f'Error processing heartbeat: {str(e)}'
            })
    
    async def handle_connection_quality(self, ws, session_id, message):
        """Handle connection quality report"""
        token = message.get('token')
        if not token:
            await ws.send_json({
                'type': 'error',
                'error': 'Missing token in connection quality report'
            })
            return
        
        data = {
            'latency_ms': message.get('latencyMs', 0),
            'missed_heartbeats': message.get('missedHeartbeats', 0),
            'connection_type': message.get('connectionType', 'unknown')
        }
        
        try:
            # Update connection quality
            quality, reconnect_recommended = await self.circuit_breakers['session_api'].execute(
                self.session_manager.update_connection_quality, session_id, token, data
            )
            
            # Send response
            await ws.send_json({
                'type': 'connection_quality_update',
                'quality': quality,
                'reconnectRecommended': reconnect_recommended
            })
            
            # Also send circuit breaker state if not closed
            for name, cb in self.circuit_breakers.items():
                if cb.state != CircuitState.CLOSED:
                    await ws.send_json({
                        'type': 'circuit_breaker_update',
                        'name': name,
                        'state': cb.state.value,
                        'resetTimeMs': cb.get_state()['time_remaining_ms']
                    })
        except CircuitOpenError as e:
            # If the circuit is open, tell the client but don't crash
            await ws.send_json({
                'type': 'connection_quality_update',
                'quality': 'degraded',  # Default to degraded if we can't check
                'reconnectRecommended': False,
                'warning': 'Service connectivity issues, some features may be limited',
                'circuitOpen': True,
                'retryAfterMs': e.remaining_ms
            })
        except Exception as e:
            logger.error(f"Error handling connection quality: {e}")
            await ws.send_json({
                'type': 'error',
                'error': f'Error processing connection quality report: {str(e)}'
            })
    
    async def broadcast_to_session(self, session_id, message):
        """Broadcast a message to all connections for a session"""
        if session_id not in self.connections:
            return
        
        # Convert dict to JSON if needed
        if isinstance(message, dict):
            json_message = json.dumps(message)
        else:
            json_message = message
        
        # Get all connections and send message
        connections = list(self.connections.get(session_id, set()))
        for ws in connections:
            try:
                if not ws.closed:
                    await ws.send_str(json_message)
            except Exception as e:
                logger.error(f"Error sending message to WebSocket: {e}")
    
    async def broadcast_circuit_breaker_update(self, circuit_name, state_info):
        """Broadcast circuit breaker state change to all connections"""
        message = {
            'type': 'circuit_breaker_update',
            'name': circuit_name,
            **state_info
        }
        
        # Broadcast to all sessions
        for session_id in self.connections.keys():
            await self.broadcast_to_session(session_id, message)
    
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
                        await ws.close()
                except Exception as e:
                    logger.error(f"Error closing WebSocket: {e}")
            
            # Clear connections
            self.connections[session_id] = set()