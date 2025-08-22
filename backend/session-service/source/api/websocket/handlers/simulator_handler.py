"""
Simplified WebSocket handlers for simulator operations.
"""
import logging
import time
from typing import Dict, Any

from opentelemetry import trace
from aiohttp import web

from source.core.session.manager import SessionManager
from source.utils.metrics import track_websocket_message, track_simulator_connection_attempt
from source.utils.tracing import optional_trace_span
from source.api.websocket.emitters import error_emitter

logger = logging.getLogger('websocket_handler_simulator')


async def handle_start_simulator(
        *,
        ws: web.WebSocketResponse,
        user_id: str,
        client_id: str,
        book_id: str,
        message: Dict[str, Any],
        session_manager: SessionManager,
        tracer: trace.Tracer,
        **kwargs
):
    """Process a start simulator request - should already be connecting"""
    with optional_trace_span(tracer, "handle_start_simulator_message") as span:
        span.set_attribute("client_id", client_id)
        span.set_attribute("user_id", user_id)
        span.set_attribute("book_id", book_id)
        
        request_id = message.get('requestId', f'start-sim-{time.time_ns()}')
        span.set_attribute("request_id", request_id)

        # Check connection status
        connection_info = session_manager.simulator_manager.get_connection_info()
        simulator_status = session_manager.get_simulator_status()
        
        if connection_info['connected']:
            response = {
                'type': 'simulator_started',
                'requestId': request_id,
                'success': True,
                'simulatorStatus': 'CONNECTED',
                'simulatorId': connection_info['simulator_id'],
                'message': 'Already connected to simulator'
            }
            logger.info(f"Simulator already connected for user {user_id}")
        elif connection_info['retrying'] or simulator_status == 'CONNECTING':
            response = {
                'type': 'simulator_started',
                'requestId': request_id,
                'success': True,
                'simulatorStatus': 'CONNECTING',
                'message': 'Connecting to simulator...'
            }
            logger.info(f"Simulator connecting for user {user_id}")
        else:
            # Try to start connection
            await session_manager.simulator_manager.start_connection_retry(book_id)
            
            response = {
                'type': 'simulator_started',
                'requestId': request_id,
                'success': True,
                'simulatorStatus': 'CONNECTING',
                'message': 'Started connecting to simulator'
            }
            logger.info(f"Started simulator connection for user {user_id}")

        try:
            if not ws.closed:
                await ws.send_json(response)
                track_websocket_message("sent", "simulator_started")
                track_simulator_connection_attempt("request")
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
    """Process a stop simulator request - just disconnect"""
    with optional_trace_span(tracer, "handle_stop_simulator_message") as span:
        span.set_attribute("client_id", client_id)
        
        request_id = message.get('requestId', f'stop-sim-{time.time_ns()}')
        span.set_attribute("request_id", request_id)

        logger.info(f"Disconnecting from simulator for user {user_id}")

        try:
            # Disconnect from simulator (doesn't destroy it)
            await session_manager.simulator_manager.disconnect()

            response = {
                'type': 'simulator_stopped',
                'requestId': request_id,
                'success': True,
                'message': 'Disconnected from simulator'
            }

            try:
                if not ws.closed:
                    await ws.send_json(response)
                    track_websocket_message("sent", "simulator_stopped")
                    track_simulator_connection_attempt("disconnect")
            except Exception as e:
                logger.error(f"Failed to send simulator_stopped for client {client_id}: {e}")
                span.record_exception(e)
                
        except Exception as e:
            logger.error(f"Error disconnecting from simulator: {e}", exc_info=True)
            await error_emitter.send_error(
                ws=ws,
                error_code="SIMULATOR_DISCONNECT_FAILED",
                message="Failed to disconnect from simulator",
                request_id=request_id,
                span=span
            )