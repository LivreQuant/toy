import logging
import json
import asyncio
import time
from aiohttp import web, WSMsgType
from typing import Dict, Set

logger = logging.getLogger('websocket_manager')

class WebSocketManager:
    """Manages WebSocket connections for session maintenance"""
    
    def __init__(self, session_manager):
        self.session_manager = session_manager
        self.connections = {}  # session_id -> set of WebSocket connections
        self.heartbeat_interval = 10  # seconds
    
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
        user_id = await self.session_manager.validate_session(session_id, token)
        if not user_id:
            await ws.send_json({
                'type': 'error',
                'error': 'Invalid session or token'
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
        session = await self.session_manager.get_session(session_id)
        frontend_connections = session.get('frontend_connections', 0)
        
        await self.session_manager.db.update_session_metadata(session_id, {
            'frontend_connections': frontend_connections + 1
        })
        
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
        # Update session activity
        await self.session_manager.db.update_session_activity(session_id)
        
        # Send heartbeat response
        await ws.send_json({
            'type': 'heartbeat_ack',
            'timestamp': int(time.time() * 1000),
            'clientTimestamp': message.get('timestamp', 0)
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
        
        quality, reconnect_recommended = await self.session_manager.update_connection_quality(
            session_id, token, data)
        
        await ws.send_json({
            'type': 'connection_quality_update',
            'quality': quality,
            'reconnectRecommended': reconnect_recommended
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