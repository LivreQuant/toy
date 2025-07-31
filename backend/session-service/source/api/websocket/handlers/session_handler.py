"""
Simplified WebSocket handlers for session operations.
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
        user_id: str,
        client_id: str,
        device_id: str,
        message: Dict[str, Any],
        session_manager: SessionManager,
        tracer: trace.Tracer,
        **kwargs
):
    """Process a session info request - connects to existing simulator"""
    with optional_trace_span(tracer, "handle_session_info_message") as span:
        span.set_attribute("client_id", client_id)

        request_id = message.get('requestId', f'session-info-{time.time_ns()}')
        span.set_attribute("request_id", request_id)

        logger.info(f"Processing session info request for user {user_id} with device {device_id}")

        # Start session (connects to existing simulator)
        success, error = await session_manager.start_session(user_id, device_id)
        
        if not success:
            logger.error(f"Failed to start session: {error}")
            await error_emitter.send_error(
                ws=ws,
                error_code="SESSION_START_FAILED",
                message=error,
                request_id=request_id,
                span=span
            )
            track_session_operation("info", "error_start")
            return

        # Get session details
        session = await session_manager.get_session()
        if not session:
            logger.warning(f"Session not found after creation")
            await error_emitter.send_error(
                ws=ws,
                error_code="SESSION_NOT_FOUND",
                message="Session not found after creation",
                request_id=request_id,
                span=span
            )
            track_session_operation("info", "error_not_found")
            return

        details = await session_manager.get_session_details()
        
        # Get simulator status (will show CONNECTING initially, then CONNECTED)
        simulator_status = session_manager.get_simulator_status()

        # Build and send response
        response = {
            'type': 'session_info',
            'requestId': request_id,
            'deviceId': details.get('device_id', device_id),
            'expiresAt': session.expires_at,
            'simulatorStatus': simulator_status
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
        user_id: str,
        client_id: str,
        device_id: str,
        message: Dict[str, Any],
        session_manager: SessionManager,
        tracer: trace.Tracer,
        **kwargs
):
   """Process a session stop request"""
   with optional_trace_span(tracer, "handle_stop_session_message") as span:
       span.set_attribute("client_id", client_id)
       
       request_id = message.get('requestId', f'stop-session-{time.time_ns()}')
       span.set_attribute("request_id", request_id)

       logger.info(f"Stopping session for user {user_id}")

       try:
           # Clean up session
           await session_manager.cleanup_session()
           await session_manager.state_manager.close()

           # Send success response
           response = {
               'type': 'session_stopped',
               'requestId': request_id,
               'success': True,
               'message': 'Session stopped and cleaned up'
           }

           try:
               if not ws.closed:
                   await ws.send_json(response)
                   track_websocket_message("sent", "session_stopped")
                   track_session_operation("stop", "success")
           except Exception as e:
               logger.error(f"Failed to send session_stopped for client {client_id}: {e}")
               span.record_exception(e)
               
           logger.info(f"Session for user {user_id} stopped successfully")

       except Exception as e:
           logger.error(f"Error stopping session: {e}", exc_info=True)
           
           await error_emitter.send_error(
               ws=ws,
               error_code="SESSION_STOP_FAILED",
               message="Failed to stop session",
               request_id=request_id,
               span=span
           )