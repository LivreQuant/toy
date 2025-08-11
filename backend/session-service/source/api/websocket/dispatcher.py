# source/api/websocket/dispatcher.py
"""
Streamlined WebSocket message dispatcher for session service.
"""
import json
import logging
from typing import Dict, Callable, Awaitable

from aiohttp import web

from source.core.session.manager import SessionManager
from source.api.websocket.exceptions import WebSocketError, ClientError
from source.api.websocket.emitters import error_emitter
from source.utils.metrics import track_websocket_message
from source.utils.tracing import trace

# Import handlers
from source.api.websocket.handlers import (
    heartbeat_handler,
    reconnect_handler,
    session_handler,
    simulator_handler,
    refresh_handler  # Add the new refresh handler
)

logger = logging.getLogger('websocket_dispatcher')

# Type definition for handler functions
HandlerFunc = Callable[..., Awaitable[None]]


class WebSocketDispatcher:
    """Parses and dispatches WebSocket messages to registered handlers."""

    def __init__(self, session_manager: SessionManager):
        """Initialize the dispatcher with a session manager."""
        self.session_manager = session_manager

        self.tracer = trace.get_tracer("websocket_dispatcher")

        # Register message handlers
        self.message_handlers: Dict[str, HandlerFunc] = {
            # Session handlers
            'heartbeat': heartbeat_handler.handle_heartbeat,
            'reconnect': reconnect_handler.handle_reconnect,
            'request_session': session_handler.handle_session_info,
            'stop_session': session_handler.handle_stop_session,

            # Simulator handlers
            'start_simulator': simulator_handler.handle_start_simulator,
            'stop_simulator': simulator_handler.handle_stop_simulator,
            
            # Delta compression handlers
            'request_full_refresh': refresh_handler.handle_request_full_refresh,
        }
        logger.info(f"WebSocketDispatcher initialized with handlers for: {list(self.message_handlers.keys())}")

    async def dispatch_message(self, ws: web.WebSocketResponse, user_id: str,
                               client_id: str, device_id: str, raw_data: str, 
                               websocket_manager=None) -> None:
        """
        Parse and dispatch an incoming WebSocket message.

        Args:
            ws: WebSocket connection
            user_id: User ID
            client_id: Client ID
            device_id: Device ID
            raw_data: Raw message data
            websocket_manager: WebSocket manager instance for refresh handling
        """
        message_type = "unknown"
        request_id = None

        try:
            # Parse JSON
            try:
                message = json.loads(raw_data)
            except json.JSONDecodeError:
                raise ClientError("Invalid JSON format", "INVALID_FORMAT")

            # Basic message validation
            if not isinstance(message, dict):
                raise ClientError("Message must be a JSON object", "INVALID_FORMAT")

            # Extract message type
            message_type = message.get('type')
            if not message_type:
                raise ClientError("Missing 'type' field", "INVALID_TYPE")

            # Extract request ID if present
            request_id = message.get('requestId')

            # Track received message
            track_websocket_message("received", message_type)

            # Find and execute handler
            handler = self.message_handlers.get(message_type)
            if not handler:
                raise ClientError(f"Unknown message type: '{message_type}'", "UNKNOWN_TYPE")

            # Execute handler
            await handler(
                ws=ws,
                user_id=user_id,
                client_id=client_id,
                device_id=device_id,
                message=message,
                session_manager=self.session_manager,
                tracer=self.tracer,
                websocket_manager=websocket_manager  # Pass websocket manager for refresh
            )

        except WebSocketError as e:
            # Handle known error types
            logger.warning(f"WebSocket error ({message_type}): {e.error_code} - {e.message}")
            await error_emitter.send_error(
                ws=ws,
                error_code=e.error_code,
                message=e.message,
                request_id=request_id
            )

        except Exception as e:
            # Handle unexpected errors
            logger.error(f"Unexpected error processing message ({message_type}): {e}", exc_info=True)
            await error_emitter.send_error(
                ws=ws,
                error_code="SERVER_ERROR",
                message="An internal server error occurred",
                request_id=request_id
            )
