# backend/session-service/source/api/websocket/handlers/simulator_handler.py
"""
WebSocket handlers for simulator operations.
Enhanced with non-blocking simulator management using gRPC status.
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
       user_id: str,
       client_id: str,
       device_id: str,
       message: Dict[str, Any],
       session_manager: SessionManager,
       tracer: trace.Tracer,
       **kwargs
):
   """
   Process a start simulator request using non-blocking background management.
   """
   with optional_trace_span(tracer, "handle_start_simulator_message") as span:
       span.set_attribute("client_id", client_id)
       span.set_attribute("user_id", user_id)
       
       request_id = message.get('requestId', f'start-sim-{time.time_ns()}')
       span.set_attribute("request_id", request_id)

       # Check if we already have a simulator via background manager
       current_status = "NONE"
       session_id = session_manager.state_manager.get_active_session_id()
       
       if session_manager.background_simulator_manager:
           current_status = session_manager.background_simulator_manager.get_session_status(session_id)
           logger.info(f"Current simulator status for session {session_id}: {current_status}")

       if current_status in ["CHECKING", "CREATING", "STARTING", "INITIALIZING", "RUNNING"]:
           # Already have a simulator in progress or running
           response = {
               'type': 'simulator_started',
               'requestId': request_id,
               'success': True,
               'simulatorStatus': current_status,
               'message': f'Simulator already {current_status.lower()}'
           }
           logger.info(f"Simulator already exists with status {current_status}")
       else:
           # Start simulator creation in background
           try:
               if session_manager.background_simulator_manager:
                   task_id = await session_manager.request_simulator_creation(user_id)
                   logger.info(f"Requested simulator creation, task_id: {task_id}")
                   
                   response = {
                       'type': 'simulator_started',
                       'requestId': request_id,
                       'success': True,
                       'simulatorStatus': 'CREATING',
                       'message': 'Simulator creation started'
                   }
               else:
                   logger.error("Background simulator manager not available")
                   await error_emitter.send_error(
                       ws=ws,
                       error_code="SIMULATOR_START_FAILED",
                       message="Simulator management not available",
                       request_id=request_id,
                       span=span
                   )
                   track_simulator_operation("start", "error_no_manager")
                   return
                   
           except Exception as e:
               logger.error(f"Failed to request simulator creation: {e}")
               await error_emitter.send_error(
                   ws=ws,
                   error_code="SIMULATOR_START_FAILED",
                   message=str(e),
                   request_id=request_id,
                   span=span
               )
               track_simulator_operation("start", "error_request")
               return

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
       user_id: str,
       client_id: str,
       device_id: str,
       message: Dict[str, Any],
       session_manager: SessionManager,
       tracer: trace.Tracer,
       **kwargs
):
   """
   Process a stop simulator request.
   """
   with optional_trace_span(tracer, "handle_stop_simulator_message") as span:
       span.set_attribute("client_id", client_id)
       
       request_id = message.get('requestId', f'stop-sim-{time.time_ns()}')
       span.set_attribute("request_id", request_id)

       # Get simulator ID from optional parameter or from session details
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