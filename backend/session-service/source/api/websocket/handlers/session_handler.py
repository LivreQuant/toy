# source/api/websocket/handlers/session_handler.py
"""
WebSocket handlers for session operations.
"""
import logging
import time
import asyncio
from typing import Dict, Any

from opentelemetry import trace
from aiohttp import web

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
    """Process a session info request."""
    with optional_trace_span(tracer, "handle_session_info_message") as span:
        span.set_attribute("client_id", client_id)

        request_id = message.get('requestId', f'session-info-{time.time_ns()}')
        span.set_attribute("request_id", request_id)

        logger.info(f"Processing session info request for user {user_id} with device {device_id}")

        # Set service to active state
        await session_manager.state_manager.set_active(user_id=user_id)
        session_id = session_manager.state_manager.get_active_session_id()

        simulator_status_server = "NONE"

        # Track any simulator we might need to reassign
        simulator_to_reassign = None

        # Check for existing active sessions for this user
        try:
            existing_sessions = await session_manager.store_manager.session_store.find_user_active_sessions(user_id)

            if existing_sessions:
                logger.info(f"Found {len(existing_sessions)} existing active sessions for user {user_id}")

                # Process existing sessions
                for existing_session in existing_sessions:
                    existing_session_id = existing_session.get('session_id')

                    if existing_session_id != session_id:  # Don't process our own session
                        logger.info(f"Deactivating existing session {existing_session_id} for user {user_id}")

                        # Check if the session has an active simulator
                        simulator = await session_manager.store_manager.simulator_store.get_simulator_by_session(
                            existing_session_id)

                        if simulator and simulator.status in [SimulatorStatus.RUNNING, SimulatorStatus.STARTING]:
                            logger.info(f"Found active simulator {simulator.simulator_id} to reassign")
                            simulator_to_reassign = simulator

                        # Update the status to INACTIVE
                        await session_manager.store_manager.session_store.update_session_status(
                            existing_session_id,
                            SessionStatus.INACTIVE
                        )
        except Exception as e:
            logger.error(f"Error checking for existing sessions: {e}")
            # Continue with session creation even if this fails

        # Create a new session
        success = await session_manager.store_manager.session_store.create_session(
            session_id, user_id, device_id, ip_address="127.0.0.1"
        )

        if success:
            logger.info(f"Successfully created user session {session_id} for user {user_id}")

            # If we have a simulator to reassign, update its session reference
            if simulator_to_reassign:
                logger.info(f"Reassigning simulator {simulator_to_reassign.simulator_id} to new session {session_id}")

                # Update simulator in database
                await session_manager.store_manager.simulator_store.update_simulator_session(
                    simulator_to_reassign.simulator_id,
                    session_id
                )

                # Update the simulator manager's tracking
                session_manager.simulator_manager.current_simulator_id = simulator_to_reassign.simulator_id
                session_manager.simulator_manager.current_endpoint = simulator_to_reassign.endpoint

                simulator_status_server = "RUNNING"
        else:
            logger.error("Failed to create user session in database")

        # Start the exchange data stream for this simulator
        try:
            if simulator_to_reassign.endpoint:
                logger.info(
                    f"Automatically starting exchange data stream for reassigned simulator {simulator_to_reassign.simulator_id}")
                stream_task = asyncio.create_task(
                    session_manager._stream_simulator_data(simulator_to_reassign.endpoint,
                                                           simulator_to_reassign.simulator_id)
                )
                stream_task.set_name(f"stream-{simulator_to_reassign.simulator_id}")

                # Register with stream manager
                if stream_task and session_manager.stream_manager:
                    session_manager.stream_manager.register_stream(session_id, stream_task)
        except Exception as e:
            logger.error(f"Error starting exchange stream for reassigned simulator: {e}")

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

        # Get details
        details = await session_manager.get_session_details()

        # Build response
        response = {
            'type': 'session_info',
            'requestId': request_id,
            'deviceId': details.get('device_id', 'unknown'),
            'expiresAt': session.expires_at,
            'simulatorStatus': simulator_status_server
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

        session_id = session_manager.state_manager.get_active_session_id()

        try:
            # Check if there's a simulator running
            simulator = await session_manager.store_manager.simulator_store.get_simulator_by_session(session_id)
            simulator_running = False
            simulator_id = None

            logger.info(f"Stopping session 2: {simulator}")

            if simulator:
                simulator_id = simulator.simulator_id
                simulator_status = simulator.status.value

                # Check if simulator is in an active state
                active_states = ['CREATING', 'STARTING', 'RUNNING']
                if simulator_id and simulator_status and simulator_status in active_states:
                    simulator_running = True

                logger.info(f"Stopping session 3: {simulator_id} {simulator_status} {simulator_running}")

            # Stop simulator if running
            if simulator_running:
                logger.info(f"Stopping simulator {simulator_id} for session")
                success, error = await session_manager.stop_simulator(simulator_id=simulator_id, force=True)

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
            else:
                logger.info(f"No simulator found.")

            logger.info(f"Stopping session 4")

            # Update session state but don't actually end it in singleton mode
            await session_manager.update_session_details({
                'device_id': None,
            })

            logger.info(f"Stopping session 5")

            # Send success response
            response = {
                'type': 'session_stopped',
                'requestId': request_id,
                'success': True,
                'message': 'Session resources cleaned up',
                'simulatorStatus': simulator_running
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