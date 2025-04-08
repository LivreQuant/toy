# websocket/emitters/error_emitter.py
"""
Handles formatting and sending standardized error messages to clients.
"""
import logging
from typing import Optional, Dict, Any, TYPE_CHECKING

from aiohttp import web
from opentelemetry import trace, context

# Assuming metrics/tracing utilities are accessible
from source.utils.metrics import track_websocket_error
from ..exceptions import WebSocketError  # Import your custom base error

# Type hint for Span if needed, already imported in dispatcher
if TYPE_CHECKING:
    # from opentelemetry.trace import Span - already imported
    pass

logger = logging.getLogger('websocket_emitter_error')


async def send_error(
        ws: web.WebSocketResponse,
        *,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        span: Optional[trace.Span] = None,
        exception: Optional[Exception] = None  # Pass original exception for logging/tracing
):
    """
    Formats and sends a standardized error payload to the client.
    Also updates tracing span and tracks error metric.

    Args:
        ws: The WebSocket connection.
        error_code: Machine-readable error code (e.g., "INVALID_INPUT").
        message: Human-readable error description.
        details: Optional dictionary with additional non-sensitive context.
        request_id: Optional client request ID to echo back.
        span: Optional OpenTelemetry span to update.
        exception: Optional original exception for context.
    """
    error_payload = {
        'type': 'error',
        'errorCode': error_code,
        'message': message,
    }
    if details:
        error_payload['details'] = details
    if request_id:
        error_payload['requestId'] = request_id

    # Update tracing span if provided
    if span and context.get_current() is not None:  # Check if span is active/sampled
        span.set_attribute("error", True)
        span.set_attribute("error.code", error_code)
        span.set_attribute("error.message", message)
        # Optionally record the exception details on the span
        if exception:
            # Check if it's one of our known types or generic
            error_type_name = exception.__class__.__name__ if isinstance(exception,
                                                                         WebSocketError) else "GenericServerError"
            span.set_attribute("error.type", error_type_name)
            # record_exception is better for full stack traces if needed, but can be verbose
            # span.record_exception(exception, attributes={"error.code": error_code})

        # Set status to ERROR
        span.set_status(trace.Status(trace.StatusCode.ERROR, description=message))

    # Attempt to send the error payload to the client
    try:
        if not ws.closed:
            await ws.send_json(error_payload)
        else:
            logger.warning(f"Cannot send error '{error_code}', WebSocket connection already closed.")
    except Exception as send_error:
        # Log if sending the error itself fails
        logger.error(f"Failed to send error payload ({error_code}) back to client: {send_error}")

    # Track the error metric using the specific error code
    track_websocket_error(error_code)  # Use error_code as the metric label
