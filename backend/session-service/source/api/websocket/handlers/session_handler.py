# source/api/websocket/handlers/session_handler.py
"""
WebSocket handlers for session operations.
"""
import logging
import time
from typing import Dict, Any

from opentelemetry import trace
from aiohttp import web

from source.core.state.manager import StateManager
from source.core.session.manager import SessionManager
from source.utils.metrics import track_websocket_message, track_session_operation
from source.utils.tracing import optional_trace_span
from source.api.websocket.emitters import error_emitter
from source.models.session import SessionStatus
from source.models.simulator import SimulatorStatus

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
    """
    Process a session info request.
    
    Args:
        ws: The WebSocket connection.
        user_id: User ID.
        client_id: Client ID.
        device_id: Device ID.
        message: The parsed message dictionary.
        session_manager: Direct access to SessionManager.
        tracer: OpenTelemetry Tracer instance.
    """
    with optional_trace_span(tracer, "handle_session_info_message") as span:
        span.set_attribute("client_id", client_id)
        
        request_id = message.get('requestId', f'session-info-{time.time_ns()}')
        span.set_attribute("request_id", request_id)

        logger.warning(f"Request session!!!")

        await session_manager.state_manager.set_active()

        session_id = session_manager.state_manager.get_active_session_id()

        # CREATE A SESSION
        success = await session_manager.store_manager.session_store.create_session(
            session_id, user_id, device_id, ip_address="127.0.0.1"
        )

        if success:
            logger.info(f"Successfully created user session {session_id} for user {user_id}")
        else:
            logger.error("Failed to create user session in database")

        session = await session_manager.get_session()
        if not session:
            logger.warning(f"Session not found for info request")
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
        user_id: str,
        client_id: str,
        device_id: str,
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
        user_id: User ID.
        client_id: Client ID.
        device_id: Device ID.
        message: The parsed message dictionary.
        session_manager: Direct access to SessionManager.
        tracer: OpenTelemetry Tracer instance.
    """
    with optional_trace_span(tracer, "handle_stop_session_message") as span:
        span.set_attribute("client_id", client_id)
        
        request_id = message.get('requestId', f'stop-session-{time.time_ns()}')
        span.set_attribute("request_id", request_id)

        logger.info(f"Stopping session 1")

        try:
            # Check if there's a simulator running
            metadata = await session_manager.get_session_metadata()
            simulator_running = False
            simulator_id = None

            logger.info(f"Stopping session 2")

            if metadata:
                simulator_id = metadata.get('simulator_id')
                simulator_status = metadata.get('simulator_status')

                # Check if simulator is in an active state
                active_states = ['CREATING', 'STARTING', 'RUNNING']
                if simulator_id and simulator_status and simulator_status in active_states:
                    simulator_running = True

            logger.info(f"Stopping session 3")

            # Stop simulator if running
            if simulator_running:
                logger.info(f"Stopping simulator {simulator_id} for session")
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

            logger.info(f"Stopping session 4")

            # Update session state but don't actually end it in singleton mode
            await session_manager.update_session_metadata({
                'device_id': None,
                'status': SessionStatus.INACTIVE.value,
                'simulator_id': None,
                'simulator_status': SimulatorStatus.NONE.value,
                'simulator_endpoint': None
            })

            logger.info(f"Stopping session 5")

            # Send success response
            response = {
                'type': 'session_stopped',
                'requestId': request_id,
                'success': True,
                'message': 'Session resources cleaned up',
                'simulatorStopped': simulator_running
            }

            logger.info(f"Stopping session 6")

            await session_manager.state_manager.close()

            logger.info(f"Stopped session 7")

            try:
                if not ws.closed:
                    await ws.send_json(response)
                    track_websocket_message("sent", "session_stopped")
                    track_session_operation("cleanup", "success")
            except Exception as e:
                logger.error(f"Failed to send session_stopped for client {client_id}: {e}")
                span.record_exception(e)
                
            # Log the session closure
            logger.info(f"Session for user {user_id} closed successfully")

        except Exception as e:
            logger.error(f"Error closing session: {e}", exc_info=True)
            
            # Send error response
            await error_emitter.send_error(
                ws=ws,
                error_code="SESSION_CLOSE_FAILED",
                message="Failed to close session",
                request_id=request_id,
                span=span,
                exception=e
            )