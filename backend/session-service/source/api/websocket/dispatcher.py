# source/api/websocket/dispatcher.py
"""
WebSocket message dispatcher.
Parses incoming messages, routes them to appropriate handlers,
and uses the error emitter to relay standardized errors to the client.
"""
import json
import logging
from typing import TYPE_CHECKING, Dict, Any, Optional, Tuple, Callable, Awaitable

from opentelemetry import trace
from aiohttp import web

from source.api.websocket.exceptions import (
    WebSocketError,
    WebSocketClientError,
    InvalidMessageFormatError
)

from source.api.websocket.handlers import (
    heartbeat_handler,
    reconnect_handler
)

from source.api.websocket.emitters import error_emitter

from source.utils.metrics import track_websocket_message
from source.utils.tracing import optional_trace_span

if TYPE_CHECKING:
    from source.api.websocket.manager import WebSocketManager

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


async def _handle_websocket_error(ws: web.WebSocketResponse, error: WebSocketError,
                                  request_id: Optional[str], message_type: str,
                                  client_id: str, span: trace.Span) -> None:
    """
    Handle known WebSocket errors.

    Args:
        ws: The WebSocket connection
        error: The WebSocketError instance
        request_id: Optional request ID from the message
        message_type: The message type
        client_id: The client ID
        span: The current tracing span
    """
    # Determine appropriate log level based on error type
    log_level = logging.WARNING if isinstance(error, WebSocketClientError) else logging.ERROR

    # Log the error
    logger.log(log_level,
               f"WebSocket Error dispatching message (type: {message_type}, client: {client_id}): "
               f"{error.error_code} - {error.message}")

    # Send error to client
    await error_emitter.send_error(
        ws=ws,
        error_code=error.error_code,
        message=error.message,
        details=error.details,
        request_id=request_id,
        span=span,
        exception=error
    )


async def _handle_unexpected_error(ws: web.WebSocketResponse, error: Exception,
                                   request_id: Optional[str], message_type: str,
                                   client_id: str, span: trace.Span) -> None:
    """
    Handle unexpected errors during message processing.

    Args:
        ws: The WebSocket connection
        error: The exception that occurred
        request_id: Optional request ID from the message
        message_type: The message type
        client_id: The client ID
        span: The current tracing span
    """
    # Log the unexpected error
    logger.error(
        f"Unexpected error dispatching WebSocket message (type: {message_type}, client: {client_id}): {error}",
        exc_info=True
    )

    # Send generic error message to client
    await error_emitter.send_error(
        ws=ws,
        error_code="INTERNAL_SERVER_ERROR",
        message="An internal server error occurred while processing your request.",
        request_id=request_id,
        span=span,
        exception=error
    )


class WebSocketDispatcher:
    """Parses and dispatches WebSocket messages to registered handlers."""

    def __init__(self, ws_manager: 'WebSocketManager'):
        """
        Initialize the dispatcher.

        Args:
            ws_manager: The WebSocket manager instance.
        """
        self.ws_manager = ws_manager
        self.tracer = trace.get_tracer("websocket_dispatcher")

        # Register message handlers: message_type -> handler_function
        self.message_handlers: Dict[str, HandlerFunc] = {
            'heartbeat': heartbeat_handler.handle_heartbeat,
            'reconnect': reconnect_handler.handle_reconnect,
            # Add other handlers here as they are created
        }
        logger.info(f"WebSocketDispatcher initialized with handlers for: {list(self.message_handlers.keys())}")

    async def dispatch_message(self, ws: web.WebSocketResponse, session_id: str,
                               user_id: Any, client_id: str, raw_data: str) -> None:
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
        request_id = None

        with optional_trace_span(self.tracer, "dispatch_websocket_message") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("client_id", client_id)
            span.set_attribute("raw_message_preview", raw_data[:100])

            try:
                # Parse the message
                message, message_type, request_id = await _parse_message(raw_data)
                span.set_attribute("message_type", message_type)
                span.set_attribute("request_id", request_id)

                # Log received message
                track_websocket_message("received", message_type)

                # Update session activity
                await self.ws_manager.register_activity(session_id)

                # Execute the appropriate handler
                await self._execute_handler(ws, session_id, user_id, client_id, message, message_type)

            except WebSocketError as e:
                # Handle specific known WebSocket errors
                await _handle_websocket_error(ws, e, request_id, message_type, client_id, span)

            except Exception as e:
                # Handle unexpected errors
                await _handle_unexpected_error(ws, e, request_id, message_type, client_id, span)

    async def _execute_handler(self, ws: web.WebSocketResponse, session_id: str,
                               user_id: Any, client_id: str, message: Dict[str, Any],
                               message_type: str) -> None:
        """
        Find and execute the appropriate message handler.

        Args:
            ws: The WebSocket connection
            session_id: The session ID
            user_id: The user ID
            client_id: The client ID
            message: The parsed message object
            message_type: The message type

        Raises:
            WebSocketClientError: If no handler exists for the message type
        """
        # Find handler
        handler = self.message_handlers.get(message_type)
        if not handler:
            raise WebSocketClientError(
                message=f"Unknown message type received: '{message_type}'",
                error_code="UNKNOWN_MESSAGE_TYPE"
            )

        # Execute handler
        await handler(
            ws=ws,
            session_id=session_id,
            user_id=user_id,
            client_id=client_id,
            message=message,
            ws_manager=self.ws_manager,
            tracer=self.tracer
        )

    def register_handler(self, message_type: str, handler: HandlerFunc) -> None:
        """
        Register a new message handler.

        Args:
            message_type: The message type to handle
            handler: The handler function
        """
        self.message_handlers[message_type] = handler
        logger.debug(f"Registered handler for message type: {message_type}")
