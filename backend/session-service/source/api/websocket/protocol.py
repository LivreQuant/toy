"""
WebSocket protocol handler.
Manages the WebSocket messaging protocol and message types.
"""
import logging
import json
import time
from typing import Dict, Any
import asyncio

from source.utils.metrics import track_websocket_message

logger = logging.getLogger('websocket_protocol')

class WebSocketProtocol:
    """WebSocket message protocol handler"""

    def __init__(self, session_manager, ws_manager):
        """
        Initialize protocol handler

        Args:
            session_manager: Session manager for session operations
            ws_manager: WebSocket manager instance
        """
        self.session_manager = session_manager
        self.exchange_client = session_manager.exchange_client
        self.ws_manager = ws_manager # Store ws_manager

        # Register message handlers
        self.message_handlers = {
            'heartbeat': self.handle_heartbeat,
            'connection_quality': self.handle_connection_quality,
            'simulator_action': self.handle_simulator_action,
            'reconnect': self.handle_reconnect,
            # Renamed subscription message type
            'subscribe_exchange_data': self.handle_subscribe_exchange_data
        }

        # Track active exchange data streams (renamed)
        self.exchange_data_streams = {}  # session_id -> streaming task


    async def handle_subscribe_exchange_data(self, ws, session_id, user_id, client_id, message):
        """
        Handle exchange data subscription request (renamed)

        Args:
            ws: WebSocket connection
            session_id: Session ID (used internally)
            user_id: User ID (used internally)
            client_id: Client ID (used internally)
            message: Message data
        """
        # Get token for authentication
        token = message.get('token')

        if not token:
            await self.send_error(ws, "Missing token in exchange data subscription request")
            return

        # Get symbols to subscribe
        symbols = message.get('symbols', [])

        # Check if simulator is running
        # Use session_manager's get_session which returns a Session object or dict
        session_obj = await self.session_manager.get_session(session_id) # Get full session object/dict

        if not session_obj:
             await self.send_error(ws, "Session not found")
             return

        # Safely access metadata attributes
        simulator_id = session_obj.get('metadata', {}).get('simulator_id')
        simulator_endpoint = session_obj.get('metadata', {}).get('simulator_endpoint')

        if not simulator_id or not simulator_endpoint:
            # Start simulator if needed
            simulator_id_res, simulator_endpoint_res, error = await self.session_manager.start_simulator(
                session_id, token, symbols
            )

            if error:
                await self.send_error(ws, f"Failed to start simulator: {error}")
                return
            # Need the endpoint to stream
            simulator_endpoint = simulator_endpoint_res


        # Check if already streaming for this session_id
        if session_id in self.exchange_data_streams and not self.exchange_data_streams[session_id].done():
            # Already streaming, potentially update symbols later if needed
            await ws.send_json({
                # Updated message type
                'type': 'exchange_data_status',
                'status': 'already_streaming',
                'symbols': symbols # Confirm symbols being streamed
            })
            track_websocket_message("sent", "exchange_data_status")
            return

        # Start streaming task (renamed function)
        self.exchange_data_streams[session_id] = asyncio.create_task(
            self._stream_exchange_data(session_id, client_id, simulator_endpoint, symbols)
        )

        # Send confirmation (updated message type)
        await ws.send_json({
            'type': 'exchange_data_status',
            'status': 'streaming_started',
            'symbols': symbols
        })
        track_websocket_message("sent", "exchange_data_status")


    async def _stream_exchange_data(self, session_id, client_id, simulator_endpoint, symbols):
        """
        Stream exchange data (market, portfolio, orders) from simulator to WebSocket clients (renamed)

        Args:
            session_id: Session ID (used internally and for logging)
            client_id: Client ID (used for logging)
            simulator_endpoint: Simulator service endpoint
            symbols: List of symbols to stream
        """
        try:
            logger.info(f"Starting exchange data stream for session {session_id}, client {client_id}, symbols: {symbols}")

            # Stream data from the exchange (renamed client method)
            async for data in self.exchange_client.stream_exchange_data(
                simulator_endpoint,
                session_id,
                client_id,
                symbols
            ):
                # Send exchange data to all clients in the session
                await self.ws_manager.broadcast_to_session(session_id, {
                     # Updated message type
                    'type': 'exchange_data',
                    'data': data # Send the comprehensive data dict
                })
                track_websocket_message("sent", "exchange_data")


        except asyncio.CancelledError:
            logger.info(f"Exchange data stream cancelled for session {session_id}")
        except Exception as e:
            logger.error(f"Error in exchange data stream for session {session_id}: {e}")
            # Try to send error to client(s) if WebSocket is still open
            try:
                 await self.ws_manager.broadcast_to_session(session_id, {
                    'type': 'error',
                    'error': f"Exchange data stream error: {str(e)}"
                 })
                 track_websocket_message("sent", "error")
            except Exception as send_err:
                 logger.error(f"Failed to send stream error to session {session_id}: {send_err}")

        finally:
            # Clean up the stream reference
            if session_id in self.exchange_data_streams:
                del self.exchange_data_streams[session_id]
                logger.info(f"Cleaned up exchange data stream task for session {session_id}")

    async def stop_exchange_data_stream(self, session_id):
        """
        Stop exchange data streaming for a session (renamed)

        Args:
            session_id: Session ID
        """
        if session_id in self.exchange_data_streams:
            stream_task = self.exchange_data_streams.pop(session_id) # Remove first
            if not stream_task.done():
                 stream_task.cancel()
                 try:
                     await stream_task # Wait for cancellation
                 except asyncio.CancelledError:
                     logger.info(f"Exchange data stream task cancelled for session {session_id}")
                 except Exception as e:
                     logger.error(f"Error during exchange stream task cancellation for session {session_id}: {e}")
            logger.info(f"Stopped exchange data stream for session {session_id}")


    async def process_message(self, ws, session_id, user_id, client_id, data):
        """
        Process an incoming message

        Args:
            ws: WebSocket connection
            session_id: Session ID (internal use)
            user_id: User ID (internal use)
            client_id: Client ID (internal use)
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
            track_websocket_message("received", message_type or "unknown")

            if not message_type:
                await self.send_error(ws, "Missing message type")
                return

            # Get handler for message type
            handler = self.message_handlers.get(message_type)

            if handler:
                # Pass internal IDs only to handlers, not to be sent back typically
                await handler(ws, session_id, user_id, client_id, message)
            else:
                logger.warning(f"Unknown message type received on session {session_id}: {message_type}")
                await self.send_error(ws, f"Unknown message type: {message_type}")

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON received on session {session_id}: {data[:100]}") # Log first 100 chars
            await self.send_error(ws, "Invalid JSON message")
        except Exception as e:
            logger.exception(f"Error processing message on session {session_id}: {e}") # Log exception with traceback
            await self.send_error(ws, "Server error processing message")

    async def handle_heartbeat(self, ws, session_id, user_id, client_id, message):
        """
        Handle heartbeat message

        Args:
            ws: WebSocket connection
            session_id: Session ID (internal use)
            user_id: User ID (internal use)
            client_id: Client ID (internal use)
            message: Message data
        """
        # Get client timestamp if provided
        client_timestamp = message.get('timestamp', 0)

        # Calculate latency if client timestamp provided
        server_timestamp = int(time.time() * 1000)
        latency = None

        if client_timestamp:
            latency = server_timestamp - client_timestamp

        # Send heartbeat response
        await ws.send_json({
            'type': 'heartbeat_ack',
            'timestamp': server_timestamp,
            'clientTimestamp': client_timestamp,
            'latency': latency
        })
        track_websocket_message("sent", "heartbeat_ack")


    async def handle_connection_quality(self, ws, session_id, user_id, client_id, message):
        """
        Handle connection quality report

        Args:
            ws: WebSocket connection
            session_id: Session ID (internal use)
            user_id: User ID (internal use)
            client_id: Client ID (internal use)
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
        track_websocket_message("sent", "connection_quality_update")


    async def handle_simulator_action(self, ws, session_id, user_id, client_id, message):
        """
        Handle simulator action request

        Args:
            ws: WebSocket connection
            session_id: Session ID (internal use)
            user_id: User ID (internal use)
            client_id: Client ID (internal use)
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
            # Start simulator returns (simulator_id, endpoint, error)
            # We don't need to send these back to the client anymore
            _, _, error = await self.session_manager.start_simulator(
                session_id, token
            )

            if error:
                await self.send_error(ws, error)
                return

            await ws.send_json({
                'type': 'simulator_update',
                'action': 'start',
                'status': 'STARTING' # Indicate status, but not internal IDs
            })
            track_websocket_message("sent", "simulator_update")


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
            track_websocket_message("sent", "simulator_update")

        else:
            await self.send_error(ws, f"Unknown simulator action: {action}")


    async def handle_reconnect(self, ws, session_id, user_id, client_id, message):
        """
        Handle reconnect request

        Args:
            ws: WebSocket connection
            session_id: Session ID (internal use)
            user_id: User ID (internal use)
            client_id: Client ID (internal use)
            message: Message data
        """
        # Get token for authentication
        token = message.get('token')
        device_id = message.get('deviceId') # Reconnect needs deviceId

        if not token or not device_id:
             await self.send_error(ws, "Missing token or deviceId in reconnect request")
             return

        # Get reconnect attempt number
        attempt = message.get('attempt', 1)

        # Process reconnection - returns (session_dict, error_message)
        session_data, error = await self.session_manager.reconnect_session(
             session_id, token, device_id, attempt # Pass deviceId
        )

        if error:
            await self.send_error(ws, error)
            return

        # Send reconnection result (Removed sensitive IDs)
        await ws.send_json({
            'type': 'reconnect_result',
            'success': True,
            # Provide only necessary non-sensitive info
            'simulatorStatus': session_data.get('simulatorStatus', 'UNKNOWN'),
            'simulatorNeedsRestart': session_data.get('simulator_needs_restart', False),
            'podName': session_data.get('metadata', {}).get('pod_name'), # Get pod name from metadata
            'timestamp': int(time.time() * 1000)
        })
        track_websocket_message("sent", "reconnect_result")


    async def send_error(self, ws, error_message):
        """
        Send error message to client

        Args:
            ws: WebSocket connection
            error_message: Error message
        """
        try:
            if not ws.closed:
                 await ws.send_json({
                     'type': 'error',
                     'error': error_message
                 })
                 track_websocket_message("sent", "error")
            else:
                 logger.warning(f"Attempted to send error to closed WebSocket: {error_message}")
        except Exception as e:
            logger.error(f"Failed to send error message via WebSocket: {e}")