# backend/session-service/source/api/websocket/manager.py
"""
WebSocket manager with configurable delta and compression support.
"""
import json
import logging
import time
import asyncio
from typing import Dict, Any
from aiohttp import web, WSMsgType
from opentelemetry import trace

from source.config import config
from source.api.websocket.utils import authenticate_websocket_request
from source.utils.tracing import optional_trace_span
from source.utils.metrics import track_websocket_message
from source.api.websocket.dispatcher import WebSocketDispatcher
from source.api.websocket.emitters import error_emitter

from source.models.exchange_data import ExchangeDataUpdate
from source.core.stream.delta_manager import DeltaManager, DeltaType


class WebSocketManager:
    def __init__(self, session_manager):
        self.session_manager = session_manager
        self.tracer = trace.get_tracer("websocket_manager")
        self.logger = logging.getLogger('websocket_manager')

        # Enhanced connection tracking
        self.active_connections: Dict[str, web.WebSocketResponse] = {}  # device_id -> ws
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}  # device_id -> metadata

        # Create a dispatcher instance
        self.dispatcher = WebSocketDispatcher(session_manager)

        # CORRECTED: Initialize delta manager with both flags
        self.delta_enabled = config.websocket.enable_delta
        self.compression_enabled = config.websocket.enable_compression
        
        if self.delta_enabled or self.compression_enabled:
            self.delta_manager = DeltaManager(
                enable_delta=self.delta_enabled,
                enable_compression=self.compression_enabled,
                compression_threshold=config.websocket.compression_threshold,
                compression_level=config.websocket.compression_level
            )
            self.logger.info(f"WebSocket Delta: {'ON' if self.delta_enabled else 'OFF'}, Compression: {'ON' if self.compression_enabled else 'OFF'}")
        else:
            self.delta_manager = None
            self.logger.info("Both delta and compression DISABLED - sending raw uncompressed data")

        # Register for exchange data
        self.session_manager.register_exchange_data_callback(self.broadcast_exchange_data)

    async def handle_connection(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connection lifecycle"""
        self.logger.info(f"WebSocket connection request received from {request.remote}")
        self.logger.info(f"Headers: {dict(request.headers)}")
        self.logger.info(f"Query params: {dict(request.query)}")

        with (optional_trace_span(self.tracer, "websocket_connection") as span):
            # Authenticate user and check for device conflicts
            try:
                self.logger.info(f"WebSocket connection request received from {request.remote}")

                user_id, book_id, device_id = await authenticate_websocket_request(request, self.session_manager)
                client_id = f"{device_id}-{time.time_ns()}"

                # Check if the user already has an active session
                session = await self.session_manager.get_session()
                if session:
                    # Get existing device ID
                    session_details = await self.session_manager.get_session_details()
                    existing_device_id = session_details.get('device_id') if session_details else None

                    # If different device ID, mark this as the new active device
                    if existing_device_id and existing_device_id != device_id:
                        self.logger.info(
                            f"User {user_id} - {book_id} connecting with new device {device_id}, replacing {existing_device_id}")
                        request['previous_device_id'] = existing_device_id

                        # Update session details with the new device ID
                        await self.session_manager.update_session_details({
                            'device_id': device_id,
                            'last_device_update': time.time()
                        })

            except Exception as auth_error:
                self.logger.warning(f"WebSocket authentication failed: {auth_error}")
                return self._reject_connection(str(auth_error))

            # Create WebSocket
            ws = web.WebSocketResponse(heartbeat=10)
            await ws.prepare(request)

            # Handle device replacement if needed
            if request.get('previous_device_id'):
                previous_device_id = request['previous_device_id']
                self.logger.warning(f"Device {device_id} is replacing existing device {previous_device_id}")

                # Find the old connection for this device
                old_ws = self.active_connections.get(previous_device_id)
                if old_ws and not old_ws.closed:
                    self.logger.info(f"Closing connection for replaced device {previous_device_id}")
                    # Force close the old connection
                    try:
                        await old_ws.close(code=1000, message=b"Connection replaced by new device")
                    except Exception as e:
                        self.logger.error(f"Error closing old connection: {e}")

                    # Remove old connection
                    if previous_device_id in self.active_connections:
                        del self.active_connections[previous_device_id]
                    if previous_device_id in self.connection_metadata:
                        del self.connection_metadata[previous_device_id]

            # Add to active connections
            self.active_connections[device_id] = ws
            self.connection_metadata[device_id] = {
                'user_id': user_id,
                'book_id': book_id,
                'client_id': client_id,
                'connected_at': time.time(),
                'last_activity': time.time()
            }

            # Connection handler
            try:
                # Process messages - use the existing method name from your codebase
                await self._connection_loop(ws, user_id, book_id, device_id, client_id)
            except Exception as e:
                self.logger.error(f"WebSocket connection error: {e}")
                await error_emitter.send_error(
                    ws=ws,
                    error_code="CONNECTION_ERROR",
                    message="Unexpected connection error"
                )
            finally:
                # Remove from active connections when done
                if device_id in self.active_connections and self.active_connections[device_id] is ws:
                    del self.active_connections[device_id]
                    if device_id in self.connection_metadata:
                        del self.connection_metadata[device_id]

                    # Reset delta state for this client if processing is enabled
                    if self.delta_manager:
                        self.delta_manager.reset_client(device_id)

            return ws
        
    async def _connection_loop(self, ws: web.WebSocketResponse, user_id: str, book_id: str, device_id: str, client_id: str):
        """Handle incoming WebSocket messages until connection closes"""
        try:
            self.logger.info(f"Starting message processing loop for client {client_id}")
            
            # Process messages until connection is closed
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    # Update last activity timestamp
                    if device_id in self.connection_metadata:
                        self.connection_metadata[device_id]['last_activity'] = time.time()
                    
                    # Process the message with websocket manager context
                    await self.dispatcher.dispatch_message(
                        ws=ws,
                        user_id=user_id,
                        book_id=book_id,
                        client_id=client_id,
                        device_id=device_id,
                        raw_data=msg.data,
                        websocket_manager=self  # Pass self for refresh handling
                    )
                elif msg.type == WSMsgType.ERROR:
                    self.logger.error(f"WebSocket connection closed with error: {ws.exception()}")
                    break
                elif msg.type == WSMsgType.CLOSE:
                    self.logger.info(f"WebSocket connection closing: {msg.data}")
                    break
        except Exception as e:
            self.logger.error(f"Error in WebSocket message loop for client {client_id}: {e}")
        finally:
            # Cleanup resources when connection ends
            await self._cleanup(ws, device_id)
            self.logger.info(f"WebSocket connection closed for client {client_id}")
            
    async def _cleanup(self, ws: web.WebSocketResponse, device_id: str):
        """Cleanup resources when connection closes"""
        if device_id in self.active_connections and self.active_connections[device_id] is ws:
            del self.active_connections[device_id]
            if device_id in self.connection_metadata:
                del self.connection_metadata[device_id]

        # Clean up delta state if processing is enabled
        if self.delta_manager:
            self.delta_manager.reset_client(device_id)

        self.logger.info(
            f"WebSocket connection for device {device_id} closed, remaining connections: {len(self.active_connections)}")

        # Clean up old delta states for any inactive clients if processing is enabled
        if self.delta_manager:
            active_device_ids = set(self.active_connections.keys())
            self.delta_manager.cleanup_old_clients(active_device_ids)

        # If all connections are closed, reset the session state
        if len(self.active_connections) == 0:
            self.logger.info("All connections closed, resetting session state to ready")
            try:
                # First stop any active streams
                if self.session_manager.stream_manager:
                    try:
                        session_id = self.session_manager.state_manager.get_active_session_id()
                        if session_id:
                            await self.session_manager.stream_manager.stop_stream(session_id)
                    except Exception as e:
                        self.logger.error(f"Error stopping streams during cleanup: {e}")

                # Reset session state but preserve simulators
                await self.session_manager.state_manager.close(keep_simulator=True)
                await self.session_manager.cleanup_session(keep_simulator=True)
            except Exception as e:
                self.logger.error(f"Error resetting session state during connection cleanup: {e}")

    async def broadcast_exchange_data(self, data: ExchangeDataUpdate):
        """Broadcast exchange data with configurable delta and compression to all active WebSocket clients"""
        if not self.active_connections:
            return

        # Convert to dictionary for processing
        data_dict = data.to_dict()
        data_id = f"{data.timestamp}-{data.update_id}"
        
        processing_type = self._get_processing_description()
        self.logger.debug(
            f"Broadcasting {processing_type} exchange data [ID: {data_id}] to {len(self.active_connections)} clients"
        )

        # Send to all active connections with appropriate method
        send_tasks = []
        for device_id, ws in list(self.active_connections.items()):
            if not ws.closed:
                if self.delta_manager:
                    send_tasks.append(
                        asyncio.ensure_future(self._send_processed_message(ws, device_id, data_dict))
                    )
                else:
                    send_tasks.append(
                        asyncio.ensure_future(self._send_raw_message(ws, device_id, data_dict))
                    )

        if send_tasks:
            # Wait for all sends to complete
            results = await asyncio.gather(*send_tasks, return_exceptions=True)
            
            # Log any errors
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    device_id = list(self.active_connections.keys())[i]
                    self.logger.error(f"Error sending to device {device_id}: {result}")
            
            self.logger.debug(f"Completed sending {processing_type} exchange data [ID: {data_id}] to {len(send_tasks)} clients")

        # Track this message
        track_websocket_message("sent_broadcast", f"exchange_data_{processing_type.lower().replace(' ', '_')}")
        
        # Log statistics periodically if enabled
        if self.delta_manager and data.timestamp % 30000 < 1000:  # Roughly every 30 seconds
            stats = self.delta_manager.get_statistics()
            self.logger.info(f"Processing stats: {stats}")

    def _get_processing_description(self) -> str:
        """Get description of current processing mode"""
        if not self.delta_enabled and not self.compression_enabled:
            return "RAW"
        elif self.delta_enabled and self.compression_enabled:
            return "DELTA+COMPRESSED"
        elif self.delta_enabled:
            return "DELTA"
        elif self.compression_enabled:
            return "COMPRESSED"
        else:
            return "RAW"

    async def _send_processed_message(self, ws: web.WebSocketResponse, device_id: str, data_dict: Dict[str, Any]):
        """Send exchange data using delta manager (with delta and/or compression)"""
        try:
            # Process message through delta manager
            delta_message = self.delta_manager.process_message(device_id, data_dict)
            
            # Create WebSocket payload
            payload = {
                'type': 'exchange_data',
                'deltaType': delta_message.type.value,  # FULL or DELTA
                'sequence': delta_message.sequence,
                'timestamp': delta_message.timestamp,
                'data': delta_message.payload,
                'compressed': delta_message.compressed,  # zlib compression flag
                'deltaEnabled': self.delta_enabled,
                'compressionEnabled': self.compression_enabled
            }
            
            # Add compression metadata if available
            if delta_message.compression_ratio:
                payload['compressionRatio'] = delta_message.compression_ratio
            if delta_message.delta_size and delta_message.original_size:
                payload['dataSavings'] = f"{((1 - delta_message.delta_size/delta_message.original_size) * 100):.1f}%"

            await ws.send_json(payload)
            
            # Track message type
            track_websocket_message("sent", f"{delta_message.type.value.lower()}{'_compressed' if delta_message.compressed else ''}")
            
        except Exception as e:
            self.logger.error(f"Error sending processed message to device {device_id}: {e}")
            # Reset client state on error to force full payload next time
            if self.delta_manager:
                self.delta_manager.reset_client(device_id)
            raise

    async def _send_raw_message(self, ws: web.WebSocketResponse, device_id: str, data_dict: Dict[str, Any]):
        """Send exchange data WITHOUT any processing (raw)"""
        try:
            # Create simple WebSocket payload without any processing
            payload = {
                'type': 'exchange_data',
                'timestamp': int(time.time() * 1000),
                'data': data_dict,
                'deltaType': 'FULL',  # Always full data
                'compressed': False,
                'deltaEnabled': False,
                'compressionEnabled': False
            }

            await ws.send_json(payload)
            
            # Track message type
            track_websocket_message("sent", "raw_full")
            
        except Exception as e:
            self.logger.error(f"Error sending raw message to device {device_id}: {e}")
            raise

    async def force_full_refresh(self, device_id: str = None):
        """Force full payload on next message for a device or all devices"""
        if not self.delta_enabled:
            # Since delta is disabled, this is a no-op
            if device_id:
                self.logger.info(f"Full refresh request for device {device_id} - delta disabled, no action needed")
            else:
                self.logger.info("Full refresh request for all devices - delta disabled, no action needed")
            return

        # Delta is enabled, reset delta state
        if device_id:
            if self.delta_manager:
                self.delta_manager.reset_client(device_id)
            self.logger.info(f"Forced full refresh for device {device_id}")
        else:
            if self.delta_manager:
                for device_id in list(self.active_connections.keys()):
                    self.delta_manager.reset_client(device_id)
            self.logger.info("Forced full refresh for all connected devices")

    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get current processing statistics"""
        if self.delta_manager:
            return self.delta_manager.get_statistics()
        else:
            return {
                'delta_enabled': False,
                'compression_enabled': False,
                'processing_disabled': True,
                'messages_processed': 0,
                'full_messages_sent': 0,
                'delta_messages_sent': 0,
                'compressed_messages_sent': 0,
                'total_original_bytes': 0,
                'total_transmitted_bytes': 0,
                'compression_ratio_sum': 0.0
            }

    async def broadcast_to_session(self, payload: Dict[str, Any]) -> int:
        """
        Broadcast a message to all devices connected to a session.
        
        Args:
            payload: The message payload
            
        Returns:
            Number of clients the message was sent to
        """
        if not self.active_connections:
            return 0

        # Get all device connections for this session
        sent_count = 0

        # In singleton mode, all connections belong to the same session
        for device_id, ws in list(self.active_connections.items()):
            if not ws.closed:
                try:
                    await ws.send_json(payload)
                    sent_count += 1
                    self.logger.debug(f"Sent status update to device {device_id}: {payload.get('type', 'unknown')}")
                except Exception as e:
                    self.logger.error(f"Error sending to device {device_id}: {e}")

        track_websocket_message("sent_broadcast", payload.get('type', 'unknown'))
        return sent_count

    def _reject_connection(self, reason: str) -> web.Response:
        """Reject WebSocket connection"""
        return web.Response(
            status=403,
            text=json.dumps({'error': reason}),
            content_type='application/json'
        )

    async def broadcast_to_device(self, device_id: str, payload: Dict[str, Any]) -> bool:
        """Send a message to a specific device"""
        if device_id not in self.active_connections:
            return False

        ws = self.active_connections[device_id]
        if ws.closed:
            return False

        try:
            await ws.send_json(payload)
            track_websocket_message("sent", payload.get('type', 'unknown'))
            return True
        except Exception as e:
            self.logger.error(f"Error sending message to device {device_id}: {e}")
            return False

    def get_connected_devices(self) -> list:
        """Get list of connected devices"""
        return list(self.active_connections.keys())

    def get_session_connections(self) -> list:
        """Get all active connections for the current session"""
        return list(self.active_connections.values())

    def get_device_connection_info(self, device_id: str) -> Dict[str, Any]:
       """Get connection info for a device"""
       if device_id not in self.connection_metadata:
           return {}
       return self.connection_metadata[device_id]

    def get_connection_count(self) -> int:
        """Get total number of active connections"""
        return len(self.active_connections)

    async def close_all_connections(self, reason: str = "Service shutting down"):
        """Close all active connections with a message"""
        if not self.active_connections:
            return

        close_tasks = []
        for device_id, ws in list(self.active_connections.items()):
            if not ws.closed:
                # Add close task
                close_tasks.append(ws.close(code=1000, message=reason.encode('utf-8')))

        # Wait for all connections to close
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)

        # Clear tracking
        self.active_connections.clear()
        self.connection_metadata.clear()