# source/api/websocket/handlers/session_handler.py
"""
WebSocket handlers for session operations.
"""
import logging
import time
from typing import Dict, Any

from opentelemetry import trace
from aiohttp import web

from source.core.session.manager import SessionManager
from source.utils.metrics import track_websocket_message, track_session_operation
from source.utils.tracing import optional_trace_span
from source.api.websocket.emitters import error_emitter

logger = logging.getLogger('websocket_handler_session')


async def handle_session_info(
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
    Process a session info request.
    
    Args:
        ws: The WebSocket connection.
        session_id: Session ID.
        user_id: User ID.
        client_id: Client ID.
        message: The parsed message dictionary.
        session_manager: Direct access to SessionManager.
        tracer: OpenTelemetry Tracer instance.
    """
    with optional_trace_span(tracer, "handle_session_info_message") as span:
        span.set_attribute("session_id", session_id)
        span.set_attribute("client_id", client_id)
        
        request_id = message.get('requestId', f'session-info-{time.time_ns()}')
        span.set_attribute("request_id", request_id)

        # Get session info
        session = await session_manager.get_session()
        if not session:
            logger.warning(f"Session {session_id} not found for info request")
            await error_emitter.send_error(
                ws=ws,
                error_code="SESSION_NOT_FOUND",
                message="Session not found",
                request_id=request_id,
                span=span
            )
            track_session_operation("info", "error_not_found")
            return

        # Get metadata
        metadata = await session_manager.get_session_metadata()
        
        # Build response
        response = {
            'type': 'session_info',
            'requestId': request_id,
            'sessionId': session_id,
            'userId': user_id,
            'status': session.status.value,
            'deviceId': metadata.get('device_id', 'unknown'),
            'createdAt': session.created_at,
            'expiresAt': session.expires_at,
            'simulatorStatus': metadata.get('simulator_status', 'NONE'),
            'simulatorId': metadata.get('simulator_id')
        }

        try:
            if not ws.closed:
                await ws.send_json(response)
                track_websocket_message("sent", "session_info")
                track_session_operation("info", "success")
        except Exception as e:
            logger.error(f"Failed to send session_info for client {client_id}: {e}")
            span.record_exception(e)


async def handle_stop_session(
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
    Process a session stop request.
    In singleton mode, we don't actually end the session, just clean up resources.
    
    Args:
        ws: The WebSocket connection.
        session_id: Session ID.
        user_id: User ID.
        client_id: Client ID.
        message: The parsed message dictionary.
        session_manager: Direct access to SessionManager.
        tracer: OpenTelemetry Tracer instance.
    """
    with optional_trace_span(tracer, "handle_stop_session_message") as span:
        span.set_attribute("session_id", session_id)
        span.set_attribute("client_id", client_id)
        
        request_id = message.get('requestId', f'stop-session-{time.time_ns()}')
        span.set_attribute("request_id", request_id)

        # Check if there's a simulator running
        metadata = await session_manager.get_session_metadata()
        simulator_running = False
        simulator_id = None

        if metadata:
            simulator_id = metadata.get('simulator_id')
            simulator_status = metadata.get('simulator_status')

            # Check if simulator is in an active state
            active_states = ['CREATING', 'STARTING', 'RUNNING']
            if simulator_id and simulator_status and simulator_status in active_states:
                simulator_running = True

        # Stop simulator if running
        if simulator_running:
            logger.info(f"Stopping simulator {simulator_id} for session {session_id}")
            success, error = await session_manager.stop_simulator()

            if not success:
                logger.warning(f"Failed to stop simulator: {error}")
                await error_emitter.send_error(
                    ws=ws,
                    error_code="SIMULATOR_STOP_FAILED",
                    message=f"Failed to stop simulator: {error}",
                    request_id=request_id,
                    span=span
                )
                track_session_operation("cleanup", "error_simulator")
                return

        # Update session state but don't actually end it in singleton mode
        await session_manager.update_session_metadata({
            'simulator_id': None,
            'simulator_status': 'NONE',
            'simulator_endpoint': None
        })

        # Send success response
        response = {
            'type': 'session_stopped',
            'requestId': request_id,
            'success': True,
            'message': 'Session resources cleaned up',
            'simulatorStopped': simulator_running
        }

        try:
            if not ws.closed:
                await ws.send_json(response)
                track_websocket_message("sent", "session_stopped")
                track_session_operation("cleanup", "success")
        except Exception as e:
            logger.error(f"Failed to send session_stopped for client {client_id}: {e}")
            span.record_exception(e)