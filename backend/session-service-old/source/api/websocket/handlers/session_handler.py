# backend/session-service/source/api/websocket/handlers/session_handler.py
"""
WebSocket handlers for session operations.
Enhanced with non-blocking simulator management using gRPC status.
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
   """Process a session info request with non-blocking simulator management"""
   with optional_trace_span(tracer, "handle_session_info_message") as span:
       span.set_attribute("client_id", client_id)

       request_id = message.get('requestId', f'session-info-{time.time_ns()}')
       span.set_attribute("request_id", request_id)

       logger.info(f"Processing session info request for user {user_id} with device {device_id}")

       # Set service to active state
       await session_manager.state_manager.set_active(user_id=user_id)
       session_id = session_manager.state_manager.get_active_session_id()

       # Handle any existing active sessions for this user
       try:
           existing_sessions = await session_manager.store_manager.session_store.find_user_active_sessions(user_id)

           if existing_sessions:
               logger.info(f"Found {len(existing_sessions)} existing active sessions for user {user_id}")

               # Process existing sessions - deactivate them
               for existing_session in existing_sessions:
                   existing_session_id = existing_session.get('session_id')

                   if existing_session_id != session_id:  # Don't process our own session
                       logger.info(f"Deactivating existing session {existing_session_id} for user {user_id}")

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

       if not success:
           logger.error("Failed to create user session in database")
           await error_emitter.send_error(
               ws=ws,
               error_code="SESSION_CREATE_FAILED",
               message="Failed to create session",
               request_id=request_id,
               span=span
           )
           track_session_operation("info", "error_create")
           return

       logger.info(f"Successfully created user session {session_id} for user {user_id}")

       # Get session for response
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

       # IMPORTANT: Start simulator check in background, don't block
       simulator_status = "CHECKING"
       try:
           if session_manager.background_simulator_manager:
               task_id = await session_manager.request_simulator_check(user_id)
               logger.info(f"Started background simulator check, task_id: {task_id}")
           else:
               logger.warning("Background simulator manager not available")
               simulator_status = "ERROR"
       except Exception as e:
           logger.error(f"Failed to start simulator check: {e}")
           simulator_status = "ERROR"

       # Build and send response immediately
       response = {
           'type': 'session_info',
           'requestId': request_id,
           'deviceId': details.get('device_id', device_id),
           'expiresAt': session.expires_at,
           'simulatorStatus': simulator_status  # Will be updated via callback/health monitoring
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
   """
   with optional_trace_span(tracer, "handle_stop_session_message") as span:
       span.set_attribute("client_id", client_id)
       
       request_id = message.get('requestId', f'stop-session-{time.time_ns()}')
       span.set_attribute("request_id", request_id)

       logger.info(f"Stopping session for user {user_id}")

       session_id = session_manager.state_manager.get_active_session_id()

       try:
           # Check if there's a simulator running via background manager
           simulator_running = False
           simulator_id = None
           
           if session_manager.background_simulator_manager:
               current_status = session_manager.background_simulator_manager.get_session_status(session_id)
               if current_status in ['INITIALIZING', 'RUNNING', 'STARTING', 'CREATING']:
                   simulator_id = session_manager.simulator_manager.current_simulator_id
                   simulator_running = True
                   logger.info(f"Session {session_id} has active simulator {simulator_id} with status {current_status}")

           # Stop simulator if running
           if simulator_running and simulator_id:
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
               logger.info(f"No active simulator found to stop.")

           # Update session state but don't actually end it in singleton mode
           await session_manager.update_session_details({
               'device_id': None,
           })

           # Send success response
           response = {
               'type': 'session_stopped',
               'requestId': request_id,
               'success': True,
               'message': 'Session resources cleaned up',
               'simulatorStopped': simulator_running
           }

           await session_manager.state_manager.close()

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
               span=span
           )