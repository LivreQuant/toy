"""
Simplified WebSocket protocol handler.
Manages the simplified WebSocket messaging protocol: status, reconnect, exchange_data stream.
"""
import logging
import json
import time
import asyncio
from typing import Dict, Any, Optional

from source.models.session import SessionStatus, ConnectionQuality
from source.models.simulator import SimulatorStatus
from source.utils.metrics import track_websocket_message, track_websocket_error
from source.utils.tracing import optional_trace_span
from opentelemetry import trace

logger = logging.getLogger('websocket_protocol')

class WebSocketProtocol:
    """Simplified WebSocket message protocol handler"""

    def __init__(self, session_manager, ws_manager):
        """
        Initialize protocol handler

        Args:
            session_manager: Session manager instance
            ws_manager: WebSocket manager instance
        """
        self.session_manager = session_manager
        self.exchange_client = session_manager.exchange_client
        self.ws_manager = ws_manager
        self.tracer = trace.get_tracer("websocket_protocol")

        # Simplified message handlers
        self.message_handlers = {
            'status': self.handle_status_request, # Client sends status/heartbeat/quality
            'reconnect': self.handle_reconnect,
            # 'simulator_action' removed - use REST API
            # 'subscribe_exchange_data' removed - streaming is automatic
        }

        # Track active exchange data streams
        self.exchange_data_streams: Dict[str, asyncio.Task] = {}  # session_id -> streaming task

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
        with optional_trace_span(self.tracer, "process_websocket_message", attributes={"app.session_id": session_id, "app.client_id": client_id}) as span:
            try:
                if isinstance(data, str):
                    message = json.loads(data)
                else:
                    message = data # Assume already dict if not string

                message_type = message.get('type')
                span.set_attribute("app.message_type", message_type or "unknown")
                track_websocket_message("received", message_type or "unknown")

                if not message_type:
                    await self.send_status_update(ws, session_id, event="error", error_message="Missing message type")
                    return

                # Update session activity on any valid message from client
                await self.session_manager.update_session_activity(session_id)

                handler = self.message_handlers.get(message_type)
                if handler:
                    await handler(ws, session_id, user_id, client_id, message)
                else:
                    logger.warning(f"Unknown message type received on session {session_id}: {message_type}")
                    await self.send_status_update(ws, session_id, event="error", error_message=f"Unknown message type: {message_type}")
                    track_websocket_error("unknown_message_type")

            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received on session {session_id}: {data[:100]}")
                span.set_attribute("error.message", "Invalid JSON")
                await self.send_status_update(ws, session_id, event="error", error_message="Invalid JSON message")
                track_websocket_error("invalid_json")
            except Exception as e:
                logger.exception(f"Error processing message on session {session_id}: {e}")
                span.record_exception(e)
                await self.send_status_update(ws, session_id, event="error", error_message="Server error processing message")
                track_websocket_error("processing_error")

    async def handle_status_request(self, ws, session_id, user_id, client_id, message):
        """
        Handle incoming status message from client (combines heartbeat & quality report).

        Args:
            ws: WebSocket connection
            session_id: Session ID (internal use)
            user_id: User ID (internal use)
            client_id: Client ID (internal use)
            message: Message data `{ "type": "status", "token": "...", "clientTimestamp": <ms>, "connectionMetrics": { ... } }`
        """
        with optional_trace_span(self.tracer, "handle_status_request", attributes={"app.session_id": session_id}) as span:
            token = message.get('token')
            if not token:
                await self.send_status_update(ws, session_id, event="error", error_message="Missing token in status message")
                return

            # Validate token (implicitly validates session existence and user match)
            # We don't need device_id here as connection is already established
            validated_user_id = await self.session_manager.validate_session(session_id, token)
            if not validated_user_id:
                # Send error status and potentially close connection if validation fails repeatedly
                await self.send_status_update(ws, session_id, event="error", error_message="Invalid session or token")
                # Consider closing ws after sending error if auth fails
                # await ws.close(code=1008, message=b'Authentication failed')
                return

            # Process optional connection metrics
            connection_metrics = message.get('connectionMetrics')
            calculated_quality = ConnectionQuality.GOOD.value # Default
            if isinstance(connection_metrics, dict):
                span.set_attribute("app.has_connection_metrics", True)
                # Use the SessionManager method to update DB and get calculated quality
                # Note: This requires SessionManager to have update_connection_quality method still
                # If that was removed, logic needs to be here or simplified. Assuming it exists for now.
                try:
                     quality_val, _ = await self.session_manager.update_connection_quality(
                         session_id, token, connection_metrics
                     )
                     calculated_quality = quality_val
                except Exception as e:
                     logger.error(f"Failed to update connection quality for {session_id}: {e}")
                     span.record_exception(e)
                     # Proceed without updated quality if metrics processing fails

            # Respond immediately with the current server status
            await self.send_status_update(ws, session_id, connection_quality=calculated_quality)


    async def handle_reconnect(self, ws, session_id, user_id, client_id, message):
        """
        Handle reconnect request

        Args:
            ws: WebSocket connection
            session_id: Session ID (internal use)
            user_id: User ID (internal use)
            client_id: Client ID (internal use)
            message: Message data `{ "type": "reconnect", "token": "...", "deviceId": "..." }`
        """
        with optional_trace_span(self.tracer, "handle_reconnect", attributes={"app.session_id": session_id}) as span:
            token = message.get('token')
            device_id = message.get('deviceId')
            attempt = message.get('attempt', 1) # Keep attempt for logging/metrics if needed

            if not token or not device_id:
                await self.send_status_update(ws, session_id, event="error", error_message="Missing token or deviceId in reconnect request")
                return

            # Process reconnection via SessionManager
            session_data_for_client, error = await self.session_manager.reconnect_session(
                session_id, token, device_id, attempt
            )

            if error:
                span.set_attribute("error.message", error)
                # Send error via status message? Or dedicated reconnect_result failure?
                # User spec implies keeping reconnect_result.
                await ws.send_json({
                     'type': 'reconnect_result',
                     'success': False,
                     'error': error
                })
                track_websocket_message("sent", "reconnect_result_failure")
                return

            # Send reconnection result (non-sensitive info)
            await ws.send_json({
                'type': 'reconnect_result',
                'success': True,
                'simulatorStatus': session_data_for_client.get('simulatorStatus', 'UNKNOWN'),
                'simulatorNeedsRestart': session_data_for_client.get('simulatorNeedsRestart', False),
                'podName': session_data_for_client.get('podName'),
                'timestamp': int(time.time() * 1000)
            })
            track_websocket_message("sent", "reconnect_result_success")

            # After successful reconnect, send initial status and start data stream if applicable
            await self.send_status_update(ws, session_id, event="reconnected")
            await self.start_exchange_data_stream_if_ready(session_id)


    async def send_status_update(self, ws, session_id: str, event: Optional[str] = None, error_message: Optional[str] = None, connection_quality: Optional[str] = None):
        """
        Fetches current status and sends a consolidated status message to the client.

        Args:
            ws: The WebSocket connection to send to.
            session_id: The session ID to fetch status for.
            event: Optional event type ('connected', 'timeout', 'error', 'shutdown', 'reconnected', 'sim_status_change').
            error_message: Optional error message if event is 'error'.
            connection_quality: Optional pre-calculated connection quality string.
        """
        if ws.closed:
            logger.debug(f"Attempted to send status update to closed websocket for session {session_id}")
            return

        status_payload = {"type": "status", "serverTimestamp": int(time.time() * 1000)}
        combined_status = {}

        try:
            # Fetch current combined status from SessionManager
            combined_status = await self.session_manager.get_combined_status(session_id)

            status_payload.update({
                "sessionStatus": combined_status.get("sessionStatus", SessionStatus.INACTIVE.value),
                "simulatorStatus": combined_status.get("simulatorStatus", SimulatorStatus.NONE.value),
                # Use provided quality if available (from client report), else fetch current
                "connectionQuality": connection_quality or combined_status.get("connectionQuality", ConnectionQuality.GOOD.value),
                "event": event,
                "errorMessage": error_message if event == "error" else None
            })

        except Exception as e:
            logger.error(f"Failed to get combined status for session {session_id}: {e}", exc_info=True)
            # Send a basic error status if fetching fails
            status_payload.update({
                "sessionStatus": SessionStatus.ERROR.value,
                "simulatorStatus": SimulatorStatus.ERROR.value,
                "connectionQuality": ConnectionQuality.POOR.value,
                "event": "error",
                "errorMessage": "Failed to retrieve server status."
            })

        try:
            await ws.send_json(status_payload)
            track_websocket_message("sent", "status")
            if event:
                 track_websocket_message("sent", f"status_event_{event}")

        except Exception as e:
            logger.error(f"Failed to send status update to session {session_id}: {e}")
            # Attempt to unregister connection if sending fails badly? Maybe handled by manager.


    # --- Exchange Data Streaming ---

    async def start_exchange_data_stream_if_ready(self, session_id: str):
        """Checks if simulator is running and starts the data stream if not already active."""
        with optional_trace_span(self.tracer, "start_exchange_data_stream_if_ready", attributes={"app.session_id": session_id}) as span:
            if session_id in self.exchange_data_streams and not self.exchange_data_streams[session_id].done():
                logger.debug(f"Exchange data stream already running for session {session_id}")
                span.add_event("Stream already running")
                return

            # Get session details to find simulator endpoint and status
            session_obj = await self.session_manager.get_session(session_id)
            if not session_obj:
                 logger.warning(f"Cannot start stream: Session {session_id} not found.")
                 span.set_attribute("error.message", "Session not found")
                 return

            sim_id = session_obj.get('metadata', {}).get('simulator_id')
            sim_endpoint = session_obj.get('metadata', {}).get('simulator_endpoint')
            sim_status_str = session_obj.get('metadata', {}).get('simulator_status', SimulatorStatus.NONE.value)
            sim_status = SimulatorStatus(sim_status_str) if sim_status_str in SimulatorStatus.__members__ else SimulatorStatus.NONE

            span.set_attribute("app.simulator_id", sim_id)
            span.set_attribute("app.simulator_status", sim_status.value)

            # Start stream only if simulator is running and endpoint exists
            if sim_status == SimulatorStatus.RUNNING and sim_endpoint:
                # Use a representative client_id for the stream task (doesn't matter much here)
                client_id_for_stream = f"streamer-{session_id}"
                logger.info(f"Simulator is running for session {session_id}. Starting exchange data stream.")
                span.add_event("Starting stream task")
                self.exchange_data_streams[session_id] = asyncio.create_task(
                    self._stream_exchange_data(session_id, client_id_for_stream, sim_endpoint)
                )
            else:
                 logger.debug(f"Simulator not running or no endpoint for session {session_id}. Stream not started.")
                 span.add_event("Stream not started (simulator not ready)")


    async def _stream_exchange_data(self, session_id, client_id_for_stream, simulator_endpoint, symbols: Optional[List[str]] = None):
        """
        Stream exchange data (market, portfolio, orders) from simulator to WebSocket clients.
        This task runs per session as long as a simulator is active and clients are connected.

        Args:
            session_id: Session ID (used internally and for logging)
            client_id_for_stream: An identifier for logging the stream source.
            simulator_endpoint: Simulator service endpoint.
            symbols: Optional list of symbols (currently not used by stream request itself, but could be).
        """
        try:
            logger.info(f"Starting background exchange data stream task for session {session_id}")

            # Stream data from the exchange client
            async for data in self.exchange_client.stream_exchange_data(
                simulator_endpoint,
                session_id,
                client_id_for_stream,
                symbols # Pass symbols if exchange client uses them
            ):
                # Check if the session still has active connections before broadcasting
                if session_id not in self.ws_manager.connections or not self.ws_manager.connections[session_id]:
                    logger.info(f"No active WebSocket connections for session {session_id}. Stopping stream task.")
                    break # Exit loop if no clients are listening

                # Send exchange data to all clients in the session via WebSocketManager
                await self.ws_manager.broadcast_to_session(session_id, {
                    'type': 'exchange_data',
                    'data': data # Send the comprehensive data dict
                })
                # Avoid tracking every single data message, too noisy
                # track_websocket_message("sent", "exchange_data")

        except asyncio.CancelledError:
            logger.info(f"Exchange data stream task cancelled for session {session_id}")
        except Exception as e:
            logger.error(f"Error in exchange data stream task for session {session_id}: {e}", exc_info=True)
            # Attempt to notify clients about the stream error via status update
            try:
                 await self.ws_manager.notify_status_update(session_id, event="error", error_message=f"Exchange data stream failed: {str(e)}")
            except Exception as notify_err:
                 logger.error(f"Failed to notify clients about stream error for session {session_id}: {notify_err}")
        finally:
            # Clean up the stream reference when task finishes or is cancelled
            if session_id in self.exchange_data_streams:
                del self.exchange_data_streams[session_id]
            logger.info(f"Exchange data stream task finished for session {session_id}")

    async def stop_exchange_data_stream(self, session_id):
        """
        Stop exchange data streaming task for a session.

        Args:
            session_id: Session ID
        """
        with optional_trace_span(self.tracer, "stop_exchange_data_stream", attributes={"app.session_id": session_id}):
            if session_id in self.exchange_data_streams:
                stream_task = self.exchange_data_streams.pop(session_id) # Remove first
                if stream_task and not stream_task.done():
                    stream_task.cancel()
                    try:
                        await stream_task # Wait for cancellation to complete
                        span.add_event("Stream task cancelled")
                    except asyncio.CancelledError:
                        logger.info(f"Exchange data stream task successfully cancelled for session {session_id}")
                        span.add_event("Stream task cancellation confirmed")
                    except Exception as e:
                        logger.error(f"Error awaiting cancelled exchange stream task for session {session_id}: {e}")
                        span.record_exception(e)
                else:
                    logger.debug(f"No active exchange data stream task found to stop for session {session_id}")
                    span.add_event("No active stream task found")
            else:
                 logger.debug(f"No exchange data stream task entry found for session {session_id}")
                 span.add_event("No stream task entry found")