"""
WebSocket protocol handler.
Manages the WebSocket messaging protocol and message types.
"""
import logging
import json
import time
from typing import Dict, Any
import asyncio

logger = logging.getLogger('websocket_protocol')

class WebSocketProtocol:
    """WebSocket message protocol handler"""
    
    def __init__(self, session_manager):
        """
        Initialize protocol handler
        
        Args:
            session_manager: Session manager for session operations
        """
        self.session_manager = session_manager
        self.exchange_client = session_manager.exchange_client
        
        # Register message handlers
        self.message_handlers = {
            'heartbeat': self.handle_heartbeat,
            'connection_quality': self.handle_connection_quality,
            'simulator_action': self.handle_simulator_action,
            'reconnect': self.handle_reconnect,
            'subscribe_market_data': self.handle_subscribe_market_data
        }
        
        # Track active market data streams
        self.market_data_streams = {}  # session_id -> streaming task
    

    async def handle_subscribe_market_data(self, ws, session_id, user_id, client_id, message):
        """
        Handle market data subscription request
        
        Args:
            ws: WebSocket connection
            session_id: Session ID
            user_id: User ID
            client_id: Client ID
            message: Message data
        """
        # Get token for authentication
        token = message.get('token')
        
        if not token:
            await self.send_error(ws, "Missing token in market data subscription request")
            return
        
        # Get symbols to subscribe
        symbols = message.get('symbols', [])
        
        # Check if simulator is running
        session = await self.session_manager.get_session(session_id)
        
        if not session:
            await self.send_error(ws, "Session not found")
            return
        
        simulator_id = session.metadata.simulator_id if hasattr(session.metadata, 'simulator_id') else None
        simulator_endpoint = session.metadata.simulator_endpoint if hasattr(session.metadata, 'simulator_endpoint') else None
        
        if not simulator_id or not simulator_endpoint:
            # Start simulator if needed
            simulator_id, simulator_endpoint, error = await self.session_manager.start_simulator(
                session_id, token, symbols
            )
            
            if error:
                await self.send_error(ws, f"Failed to start simulator: {error}")
                return
        
        # Check if already streaming
        if session_id in self.market_data_streams and not self.market_data_streams[session_id].done():
            # Already streaming, just update symbols if needed
            # (This would require additional implementation to update active streams)
            await ws.send_json({
                'type': 'market_data_status',
                'status': 'already_streaming',
                'symbols': symbols
            })
            return
        
        # Start streaming task
        self.market_data_streams[session_id] = asyncio.create_task(
            self._stream_market_data(ws, session_id, client_id, simulator_endpoint, symbols)
        )
        
        # Send confirmation
        await ws.send_json({
            'type': 'market_data_status',
            'status': 'streaming_started',
            'symbols': symbols
        })
    

    async def _stream_market_data(self, ws, session_id, client_id, simulator_endpoint, symbols):
        """
        Stream market data from simulator to WebSocket
        
        Args:
            ws: WebSocket connection
            session_id: Session ID
            client_id: Client ID
            simulator_endpoint: Simulator service endpoint
            symbols: List of symbols to stream
        """
        try:
            logger.info(f"Starting market data stream for session {session_id}, client {client_id}, symbols: {symbols}")
            
            # Stream data from the exchange
            async for data in self.exchange_client.stream_market_data(
                simulator_endpoint,
                session_id,
                client_id,
                symbols
            ):
                # Check if WebSocket is still open
                if ws.closed:
                    logger.info(f"WebSocket closed, stopping market data stream for {session_id}")
                    break
                
                # Send market data to client
                await ws.send_json({
                    'type': 'market_data',
                    'data': data
                })
                
        except asyncio.CancelledError:
            logger.info(f"Market data stream cancelled for session {session_id}")
        except Exception as e:
            logger.error(f"Error in market data stream for session {session_id}: {e}")
            
            # Try to send error to client if WebSocket is still open
            if not ws.closed:
                try:
                    await ws.send_json({
                        'type': 'error',
                        'error': f"Market data stream error: {str(e)}"
                    })
                except:
                    pass
        finally:
            # Clean up the stream reference
            if session_id in self.market_data_streams:
                del self.market_data_streams[session_id]
    
    async def stop_market_data_stream(self, session_id):
        """
        Stop market data streaming for a session
        
        Args:
            session_id: Session ID
        """
        if session_id in self.market_data_streams and not self.market_data_streams[session_id].done():
            self.market_data_streams[session_id].cancel()
            try:
                await self.market_data_streams[session_id]
            except asyncio.CancelledError:
                pass
            del self.market_data_streams[session_id]
            logger.info(f"Stopped market data stream for session {session_id}")

    async def process_message(self, ws, session_id, user_id, client_id, data):
        """
        Process an incoming message
        
        Args:
            ws: WebSocket connection
            session_id: Session ID
            user_id: User ID
            client_id: Client ID
            data: Message data (string or dict)
        """
        try:
            # Parse message if needed
            if isinstance(data, str):
                message = json.loads(data)
            else:
                message = data
            
            # Update session activity on any message
            await self.session_manager.update_session_activity(session_id)
            
            # Get message type
            message_type = message.get('type')
            
            if not message_type:
                await self.send_error(ws, "Missing message type")
                return
            
            # Get handler for message type
            handler = self.message_handlers.get(message_type)
            
            if handler:
                await handler(ws, session_id, user_id, client_id, message)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                await self.send_error(ws, f"Unknown message type: {message_type}")
        
        except json.JSONDecodeError:
            await self.send_error(ws, "Invalid JSON message")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await self.send_error(ws, "Server error processing message")
    
    async def handle_heartbeat(self, ws, session_id, user_id, client_id, message):
        """
        Handle heartbeat message
        
        Args:
            ws: WebSocket connection
            session_id: Session ID
            user_id: User ID
            client_id: Client ID
            message: Message data
        """
        # Get client timestamp if provided
        client_timestamp = message.get('timestamp', 0)
        
        # Calculate latency if client timestamp provided
        server_timestamp = int(time.time() * 1000)
        latency = None
        
        if client_timestamp:
            latency = server_timestamp - client_timestamp
        
        # Update session activity
        await self.session_manager.update_session_activity(session_id)
        
        # Send heartbeat response
        await ws.send_json({
            'type': 'heartbeat_ack',
            'timestamp': server_timestamp,
            'clientTimestamp': client_timestamp,
            'latency': latency
        })
    
    async def handle_connection_quality(self, ws, session_id, user_id, client_id, message):
        """
        Handle connection quality report
        
        Args:
            ws: WebSocket connection
            session_id: Session ID
            user_id: User ID
            client_id: Client ID
            message: Message data
        """
        # Get token for authentication
        token = message.get('token')
        
        if not token:
            await self.send_error(ws, "Missing token in connection quality report")
            return
        
        # Get metrics
        metrics = {
            'latency_ms': message.get('latencyMs', 0),
            'missed_heartbeats': message.get('missedHeartbeats', 0),
            'connection_type': message.get('connectionType', 'websocket')
        }
        
        # Update connection quality
        quality, reconnect_recommended = await self.session_manager.update_connection_quality(
            session_id, token, metrics
        )
        
        # Send response
        await ws.send_json({
            'type': 'connection_quality_update',
            'quality': quality,
            'reconnectRecommended': reconnect_recommended
        })
    
    async def handle_simulator_action(self, ws, session_id, user_id, client_id, message):
        """
        Handle simulator action request
        
        Args:
            ws: WebSocket connection
            session_id: Session ID
            user_id: User ID
            client_id: Client ID
            message: Message data
        """
        # Get token for authentication
        token = message.get('token')
        
        if not token:
            await self.send_error(ws, "Missing token in simulator action request")
            return
        
        # Get action
        action = message.get('action')
        
        if not action:
            await self.send_error(ws, "Missing action in simulator action request")
            return
        
        # Handle action
        if action == 'start':
            simulator_id, endpoint, error = await self.session_manager.start_simulator(
                session_id, token
            )
            
            if error:
                await self.send_error(ws, error)
                return
            
            await ws.send_json({
                'type': 'simulator_update',
                'action': 'start',
                'status': 'STARTING',
                'simulatorId': simulator_id,
                'simulatorEndpoint': endpoint
            })
            
        elif action == 'stop':
            success, error = await self.session_manager.stop_simulator(
                session_id, token
            )
            
            if not success:
                await self.send_error(ws, error)
                return
            
            await ws.send_json({
                'type': 'simulator_update',
                'action': 'stop',
                'status': 'STOPPED'
            })
            
        else:
            await self.send_error(ws, f"Unknown simulator action: {action}")
    
    async def handle_reconnect(self, ws, session_id, user_id, client_id, message):
        """
        Handle reconnect request
        
        Args:
            ws: WebSocket connection
            session_id: Session ID
            user_id: User ID
            client_id: Client ID
            message: Message data
        """
        # Get token for authentication
        token = message.get('token')
        
        if not token:
            await self.send_error(ws, "Missing token in reconnect request")
            return
        
        # Get reconnect attempt number
        attempt = message.get('attempt', 1)
        
        # Process reconnection
        session_data, error = await self.session_manager.reconnect_session(
            session_id, token, attempt
        )
        
        if error:
            await self.send_error(ws, error)
            return
        
        # Send reconnection result
        await ws.send_json({
            'type': 'reconnect_result',
            'success': True,
            'sessionId': session_data['session_id'],
            'simulatorId': session_data.get('simulator_id'),
            'simulatorStatus': session_data.get('simulator_status', 'UNKNOWN'),
            'podName': session_data.get('pod_name'),
            'timestamp': int(time.time() * 1000)
        })
    
    async def send_error(self, ws, error_message):
        """
        Send error message to client
        
        Args:
            ws: WebSocket connection
            error_message: Error message
        """
        await ws.send_json({
            'type': 'error',
            'error': error_message
        })