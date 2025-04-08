# websocket/dispatcher.py
"""
WebSocket message dispatcher.
Parses incoming messages, routes them to appropriate handlers,
and uses the error emitter to relay standardized errors to the client.
"""
import json
import logging
from typing import TYPE_CHECKING, Callable, Dict, Any, Awaitable, Optional

from opentelemetry import trace, context
from aiohttp import web

# Import handlers
from .handlers import heartbeat_handler, reconnect_handler

# Import custom exceptions
from .exceptions import (
    WebSocketError,
    WebSocketClientError,
    WebSocketServerError,
    InvalidMessageFormatError # Specific client error type
)

# Import Emitter for sending errors
from .emitters import error_emitter

# Assuming these utilities exist and are correctly path-imported
from source.utils.metrics import track_websocket_message
# track_websocket_error is now called inside error_emitter
from source.utils.tracing import optional_trace_span

# Type hint for WebSocketManager and SessionManager without circular import
if TYPE_CHECKING:
    from .manager import WebSocketManager
    from source.core.session_manager import SessionManager

logger = logging.getLogger('websocket_dispatcher')

# Define a type alias for the expected handler function signature
HandlerFunc = Callable[..., Awaitable[None]]


class WebSocketDispatcher:
    """Parses and dispatches WebSocket messages to registered handlers."""

    def __init__(self, session_manager: 'SessionManager', ws_manager: 'WebSocketManager'):
        """
        Initialize the dispatcher.

        Args:
            session_manager: The session manager instance.
            ws_manager: The WebSocket manager instance.
        """
        self.session_manager = session_manager
        self.ws_manager = ws_manager
        self.tracer = trace.get_tracer("websocket_dispatcher")

        # Register message handlers: message_type -> handler_function
        self.message_handlers: Dict[str, HandlerFunc] = {
            'heartbeat': heartbeat_handler.handle_heartbeat,
            'reconnect': reconnect_handler.handle_reconnect,
        }
        logger.info(f"WebSocketDispatcher initialized with handlers for: {list(self.message_handlers.keys())}")

    async def dispatch_message(self, ws: web.WebSocketResponse, session_id: str, user_id: Any, client_id: str, raw_data: str):
        """
        Parse and dispatch a single incoming WebSocket message.

        Args:
            ws: The WebSocket connection instance.
            session_id: The session ID associated with the connection.
            user_id: The user ID associated with the connection.
            client_id: The client ID for this specific connection.
            raw_data: The raw message data string received.
        """
        message = None
        message_type = "unknown"
        # Propagate active span context if available
        current_span: Optional[trace.Span] = trace.get_current_span()
        tracer_context = context.attach(trace.set_span_in_context(current_span)) if current_span else None

        with optional_trace_span(self.tracer, "dispatch_websocket_message", context=tracer_context) as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("client_id", client_id)
            span.set_attribute("raw_message_preview", raw_data[:100])

            try:
                # 1. Parse JSON
                try:
                    message = json.loads(raw_data)
                    request_id = message.get('requestId') if isinstance(message, dict) else None # Get request ID early
                except json.JSONDecodeError as e:
                    # Use specific custom exception
                    raise InvalidMessageFormatError(f"Invalid JSON received: {e}") from e

                # 2. Extract and Validate Message Type
                message_type = message.get('type')
                if not isinstance(message_type, str) or not message_type:
                    raise WebSocketClientError(
                         message="Message 'type' field is missing or not a string.",
                         error_code="INVALID_MESSAGE_TYPE_FIELD"
                     )

                span.set_attribute("message_type", message_type)
                track_websocket_message("received", message_type) # Track received metric

                # 3. Find Handler
                handler = self.message_handlers.get(message_type)
                if not handler:
                    raise WebSocketClientError(
                        message=f"Unknown message type received: '{message_type}'",
                        error_code="UNKNOWN_MESSAGE_TYPE"
                    )

                # 4. Update Session Activity
                await self.session_manager.update_session_activity(session_id)

                # 5. Execute Handler
                await handler(
                    ws=ws,
                    session_id=session_id,
                    user_id=user_id,
                    client_id=client_id,
                    message=message,
                    session_manager=self.session_manager,
                    ws_manager=self.ws_manager,
                    tracer=self.tracer
                )

            # 6. Handle Specific Known Errors (using Error Emitter)
            except WebSocketError as e:
                # Includes WebSocketClientError, WebSocketSessionError, etc.
                log_level = logging.WARNING if isinstance(e, WebSocketClientError) else logging.ERROR
                logger.log(log_level, f"WebSocket Error dispatching message (type: {message_type}, client: {client_id}): {e.error_code} - {e.message}")
                # Call the centralized error emitter
                await error_emitter.send_error(
                    ws=ws,
                    error_code=e.error_code,
                    message=e.message,
                    details=e.details,
                    request_id=request_id, # Use request_id obtained earlier
                    span=span,
                    exception=e
                )

            # 7. Handle Unexpected Errors (using Error Emitter)
            except Exception as e:
                logger.error(
                    f"Unexpected error dispatching WebSocket message (type: {message_type}, client: {client_id}): {e}",
                    exc_info=True
                )
                # No need to call span.record_exception here, send_error handles span update
                # Call the centralized error emitter with generic server error info
                await error_emitter.send_error(
                     ws=ws,
                     error_code="INTERNAL_SERVER_ERROR",
                     message="An internal server error occurred while processing your request.",
                     request_id=request_id, # Use request_id obtained earlier
                     span=span,
                     exception=e # Pass original exception for tracing/logging context
                )
