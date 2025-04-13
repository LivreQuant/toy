# source/api/websocket/handlers/simulator_handler.py
"""
WebSocket handlers for simulator operations.
"""
import logging
import time
from typing import Dict, Any

from opentelemetry import trace
from aiohttp import web

from source.core.session.manager import SessionManager
from source.utils.metrics import track_websocket_message, track_simulator_operation
from source.utils.tracing import optional_trace_span
from source.api.websocket.emitters import error_emitter

logger = logging.getLogger('websocket_handler_simulator')


async def handle_start_simulator(
        *,
        ws: web.WebSocketResponse,
        session_id: str,
        user_id: str,
        client_id: str,
        message: Dict[str, Any],
        session_manager: SessionManager,
        tracer: trace.Tracer,
        **kwargs
):
    """
    Process a start simulator request.
    
    Args:
        ws: The WebSocket connection.
        session_id: Session ID.
        user_id: User ID.
        client_id: Client ID.
        message: The parsed message dictionary.
        session_manager: Direct access to SessionManager.
        tracer: OpenTelemetry Tracer instance.
    """
    with optional_trace_span(tracer, "handle_start_simulator_message") as span:
        span.set_attribute("session_id", session_id)
        span.set_attribute("client_id", client_id)
        span.set_attribute("user_id", user_id)
        
        request_id = message.get('requestId', f'start-sim-{time.time_ns()}')
        span.set_attribute("request_id", request_id)

        # Start simulator (using user ID from validated token)
        simulator_id, endpoint, error = await session_manager.start_simulator(user_id)

        # Set span attributes for tracing
        span.set_attribute("simulator_id", simulator_id or "none")
        span.set_attribute("endpoint", endpoint or "none")

        if error:
            span.set_attribute("error", error)
            await error_emitter.send_error(
                ws=ws,
                error_code="SIMULATOR_START_FAILED",
                message=error,
                request_id=request_id,
                span=span
            )
            track_simulator_operation("start", "error_validation")
            return

        # Send success response
        response = {
            'type': 'simulator_started',
            'requestId': request_id,
            'success': True,
            'simulatorId': simulator_id,
            'status': 'STARTING',
        }

        try:
            if not ws.closed:
                await ws.send_json(response)
                track_websocket_message("sent", "simulator_started")
                track_simulator_operation("start", "success")
        except Exception as e:
            logger.error(f"Failed to send simulator_started for client {client_id}: {e}")
            span.record_exception(e)


async def handle_stop_simulator(
        *,
        ws: web.WebSocketResponse,
        session_id: str,
        user_id: str,
        client_id: str,
        message: Dict[str, Any],
        session_manager: SessionManager,
        tracer: trace.Tracer,
        **kwargs
):
    """
    Process a stop simulator request.
    
    Args:
        ws: The WebSocket connection.
        session_id: Session ID.
        user_id: User ID.
        client_id: Client ID.
        message: The parsed message dictionary.
        session_manager: Direct access to SessionManager.
        tracer: OpenTelemetry Tracer instance.
    """
    with optional_trace_span(tracer, "handle_stop_simulator_message") as span:
        span.set_attribute("session_id", session_id)
        span.set_attribute("client_id", client_id)
        
        request_id = message.get('requestId', f'stop-sim-{time.time_ns()}')
        span.set_attribute("request_id", request_id)

        # Get simulator ID from optional parameter or from session metadata
        simulator_id = message.get('simulatorId')
        force_stop = message.get('force', False)
        
        # Stop simulator associated with session
        success, error = await session_manager.stop_simulator(simulator_id, force_stop)

        # Set span attributes for tracing
        span.set_attribute("stop_success", success)

        if not success:
            span.set_attribute("error", error)
            await error_emitter.send_error(
                ws=ws,
                error_code="SIMULATOR_STOP_FAILED",
                message=error,
                request_id=request_id,
                span=span
            )
            track_simulator_operation("stop", "error_validation")
            return

        # Send success response
        response = {
            'type': 'simulator_stopped',
            'requestId': request_id,
            'success': True
        }

        try:
            if not ws.closed:
                await ws.send_json(response)
                track_websocket_message("sent", "simulator_stopped")
                track_simulator_operation("stop", "success")
        except Exception as e:
            logger.error(f"Failed to send simulator_stopped for client {client_id}: {e}")
            span.record_exception(e)