import logging
import json
import time
import asyncio
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger('websocket_protocol')

class WebSocketProtocol:
    """Protocol handler for WebSocket messages"""
    
    def __init__(self, session_manager):
        self.session_manager = session_manager
        
        # Register message type handlers
        self.message_handlers = {
            'heartbeat': self.handle_heartbeat,
            'connection_quality': self.handle_connection_quality,
            'subscribe': self.handle_subscribe,
            'unsubscribe': self.handle_unsubscribe,
            'reconnect': self.handle_reconnect
        }
        
        # Session metrics tracking
        self.session_metrics = {}  # session_id -> metrics
    
    async def process_message(self, ws, session_id, user_id, message_data):
        """Process an incoming WebSocket message"""
        try:
            # Parse message if it's a string
            if isinstance(message_data, str):
                message = json.loads(message_data)
            else:
                message = message_data
            
            # Get message type
            message_type = message.get('type')
            
            if message_type in self.message_handlers:
                # Pass to appropriate handler
                await self.message_handlers[message_type](ws, session_id, user_id, message)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                await self.send_error(ws, f"Unknown message type: {message_type}")
        
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON message: {message_data}")
            await self.send_error(ws, "Invalid JSON message")
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await self.send_error(ws, f"Error processing message: {str(e)}")
    
    async def handle_heartbeat(self, ws, session_id, user_id, message):
        """Handle heartbeat message"""
        # Get client timestamp
        client_timestamp = message.get('timestamp', 0)
        
        # Update session activity
        await self.session_manager.db.update_session_activity(session_id)
        
        # Calculate round-trip latency if we have previous heartbeat data
        latency = None
        if session_id in self.session_metrics and 'last_heartbeat_sent' in self.session_metrics[session_id]:
            last_sent = self.session_metrics[session_id]['last_heartbeat_sent']
            latency = int(time.time() * 1000) - last_sent
        
        # Update session metrics
        if session_id not in self.session_metrics:
            self.session_metrics[session_id] = {}
        
        self.session_metrics[session_id].update({
            'last_heartbeat': time.time(),
            'client_timestamp': client_timestamp,
            'latency': latency
        })
        
        # Send heartbeat response
        server_timestamp = int(time.time() * 1000)
        await ws.send_json({
            'type': 'heartbeat_ack',
            'timestamp': server_timestamp,
            'clientTimestamp': client_timestamp,
            'latency': latency
        })
    
    async def handle_connection_quality(self, ws, session_id, user_id, message):
        """Handle connection quality report from client"""
        # Extract token
        token = message.get('token')
        if not token:
            await self.send_error(ws, "Missing token in connection quality report")
            return
        
        # Get connection quality data
        data = {
            'latency_ms': message.get('latencyMs', 0),
            'missed_heartbeats': message.get('missedHeartbeats', 0),
            'connection_type': message.get('connectionType', 'unknown')
        }
        
        # Update connection quality
        quality, reconnect_recommended = await self.session_manager.update_connection_quality(
            session_id, token, data)
        
        # Send response
        await ws.send_json({
            'type': 'connection_quality_update',
            'quality': quality,
            'reconnectRecommended': reconnect_recommended
        })
        
        # Update metrics
        if session_id not in self.session_metrics:
            self.session_metrics[session_id] = {}
        
        self.session_metrics[session_id].update({
            'connection_quality': quality,
            'latency_ms': data['latency_ms'],
            'missed_heartbeats': data['missed_heartbeats'],
            'connection_type': data['connection_type']
        })
    
    async def handle_subscribe(self, ws, session_id, user_id, message):
        """Handle subscription request for specific data types"""
        # Get subscription type
        subscription_type = message.get('dataType')
        symbols = message.get('symbols', [])
        
        if not subscription_type:
            await self.send_error(ws, "Missing dataType in subscribe message")
            return
        
        # Update session subscriptions
        await self.session_manager.db.update_session_metadata(session_id, {
            'subscriptions': {
                subscription_type: {
                    'symbols': symbols,
                    'timestamp': time.time()
                }
            }
        })
        
        # Acknowledge subscription
        await ws.send_json({
            'type': 'subscription_ack',
            'dataType': subscription_type,
            'symbols': symbols
        })
    
    async def handle_unsubscribe(self, ws, session_id, user_id, message):
        """Handle unsubscribe request"""
        # Get subscription type
        subscription_type = message.get('dataType')
        
        if not subscription_type:
            await self.send_error(ws, "Missing dataType in unsubscribe message")
            return
        
        # Update session subscriptions
        session = await self.session_manager.get_session(session_id)
        if session and 'subscriptions' in session:
            subscriptions = session.get('subscriptions', {})
            if subscription_type in subscriptions:
                del subscriptions[subscription_type]
                
                await self.session_manager.db.update_session_metadata(session_id, {
                    'subscriptions': subscriptions
                })
        
        # Acknowledge unsubscribe
        await ws.send_json({
            'type': 'unsubscription_ack',
            'dataType': subscription_type
        })
    
    async def handle_reconnect(self, ws, session_id, user_id, message):
        """Handle explicit reconnect request"""
        token = message.get('token')
        attempt = message.get('attempt', 1)
        
        if not token:
            await self.send_error(ws, "Missing token in reconnect message")
            return
        
        # Perform reconnection
        result, error = await self.session_manager.reconnect_session(
            session_id, token, attempt)
        
        if not result:
            await self.send_error(ws, error)
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
    
    async def send_error(self, ws, error_message):
        """Send error message to client"""
        try:
            await ws.send_json({
                'type': 'error',
                'error': error_message
            })
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")
    
    def get_session_metric(self, session_id, metric_name, default=None):
        """Get a specific metric for a session"""
        if session_id not in self.session_metrics:
            return default
        
        return self.session_metrics[session_id].get(metric_name, default)
    
    async def send_system_notification(self, ws, message_type, data):
        """Send system notification to client"""
        try:
            notification = {
                'type': message_type,
                **data
            }
            await ws.send_json(notification)
        except Exception as e:
            logger.error(f"Failed to send system notification: {e}")