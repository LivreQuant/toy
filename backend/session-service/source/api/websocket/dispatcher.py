# source/api/websocket/dispatcher.py
"""
WebSocket message dispatcher for single-user mode.
Parses incoming messages and routes them to appropriate handlers.
"""
import json
import logging
from typing import Dict, Any, Optional, Tuple, Callable, Awaitable

from opentelemetry import trace
from aiohttp import web

from source.core.session.manager import SessionManager
from source.api.websocket.exceptions import (
    WebSocketError,
    WebSocketClientError,
    InvalidMessageFormatError
)

from source.api.websocket.handlers import (
    heartbeat_handler,
    reconnect_handler,
    session_handler,
    simulator_handler
)

from source.api.websocket.emitters import error_emitter

from source.utils.metrics import track_websocket_message
from source.utils.tracing import optional_trace_span

logger = logging.getLogger('websocket_dispatcher')

# Type definition for handler functions
HandlerFunc = Callable[..., Awaitable[None]]


async def _parse_message(raw_data: str) -> Tuple[Dict[str, Any], str, Optional[str]]:
    """
    Parse and validate the raw message data.
    
    Args:
        raw_data: The raw message string
        
    Returns:
        Tuple of (parsed_message, message_type, request_id)
        
    Raises:
        InvalidMessageFormatError: If JSON parsing fails
        WebSocketClientError: If message validation fails
    """
    try:
        # Parse JSON
        message = json.loads(raw_data)
    except json.JSONDecodeError as e:
        # Specific custom exception for invalid JSON
        raise InvalidMessageFormatError(f"Invalid JSON received: {e}") from e

    # Get request ID if available
    request_id = message.get('requestId') if isinstance(message, dict) else None

    # Extract and validate message type
    if not isinstance(message, dict):
        raise WebSocketClientError(
            message="Message must be a JSON object.",
            error_code="INVALID_MESSAGE_FORMAT"
        )

    message_type = message.get('type')
    if not isinstance(message_type, str) or not message_type:
        raise WebSocketClientError(
            message="Message 'type' field is missing or not a string.",
            error_code="INVALID_MESSAGE_TYPE_FIELD"
        )

    return message, message_type, request_id


class WebSocketDispatcher:
    """Parses and dispatches WebSocket messages to registered handlers."""

    def __init__(self, session_manager: SessionManager):
        """
        Initialize the dispatcher.

        Args:
            session_manager: The session manager instance.
        """
        self.session_manager = session_manager
        self.tracer = trace.get_tracer("websocket_dispatcher")

        # Register message handlers: message_type -> handler_function
        self.message_handlers: Dict[str, HandlerFunc] = {
            # Original handlers
            'heartbeat': heartbeat_handler.handle_heartbeat,
            'reconnect': reconnect_handler.handle_reconnect,
            
            # Session handlers
            'request_session_info': session_handler.handle_session_info,
            'stop_session': session_handler.handle_stop_session,
            
            # Simulator handlers
            'start_simulator': simulator_handler.handle_start_simulator,
            'stop_simulator': simulator_handler.handle_stop_simulator,
        }
        logger.info(f"WebSocketDispatcher initialized with handlers for: {list(self.message_handlers.keys())}")

    async def dispatch_message(self, ws: web.WebSocketResponse, user_id: str,
                               client_id: str, device_id: str, raw_data: str) -> None:
        """
        Parse and dispatch a single incoming WebSocket message.

        Args:
            ws: The WebSocket connection instance.
            user_id: The user ID associated with the connection.
            client_id: The client ID for this specific connection.
            device_id: The device ID for this specific connection.
            raw_data: The raw message data string received.
        """
        message_type = "unknown"
        request_id = None

        with optional_trace_span(self.tracer, "dispatch_websocket_message") as span:
            span.set_attribute("client_id", client_id)
            span.set_attribute("device_id", device_id)
            span.set_attribute("raw_message_preview", raw_data[:100])

            try:
                # Parse the message
                message, message_type, request_id = await _parse_message(raw_data)
                span.set_attribute("message_type", message_type)
                span.set_attribute("request_id", request_id)

                # Log received message
                track_websocket_message("received", message_type)

                # Execute the appropriate handler
                await self._execute_handler(ws, user_id, client_id, device_id, message, message_type)

            except WebSocketError as e:
                # Log the error
                log_level = logging.WARNING if isinstance(e, WebSocketClientError) else logging.ERROR
                logger.log(log_level,
                           f"WebSocket Error dispatching message (type: {message_type}, client: {client_id}): "
                           f"{e.error_code} - {e.message}")

                # Send error to client
                await error_emitter.send_error(
                    ws=ws,
                    error_code=e.error_code,
                    message=e.message,
                    details=getattr(e, 'details', None),
                    request_id=request_id,
                    span=span,
                    exception=e
                )

            except Exception as e:
                # Log the unexpected error
                logger.error(
                    f"Unexpected error dispatching WebSocket message (type: {message_type}, client: {client_id}): {e}",
                    exc_info=True
                )

                # Send generic error message to client
                await error_emitter.send_error(
                    ws=ws,
                    error_code="INTERNAL_SERVER_ERROR",
                    message="An internal server error occurred while processing your request.",
                    request_id=request_id,
                    span=span,
                    exception=e
                )

    async def _execute_handler(self, ws: web.WebSocketResponse, user_id: Any,
                               client_id: str, device_id: str, message: Dict[str, Any],
                               message_type: str) -> None:
        """
        Find and execute the appropriate message handler.
        """
        # Find handler
        handler = self.message_handlers.get(message_type)
        if not handler:
            raise WebSocketClientError(
                message=f"Unknown message type received: '{message_type}'",
                error_code="UNKNOWN_MESSAGE_TYPE"
            )

        # Execute handler with direct access to session_manager
        await handler(
            ws=ws,
            user_id=user_id,
            client_id=client_id,
            device_id=device_id,
            message=message,
            session_manager=self.session_manager,
            tracer=self.tracer
        )
        