# source/api/websocket/handlers/refresh_handler.py
"""
Handler for full refresh requests from clients.
"""
import logging
from typing import Dict, Any

from opentelemetry import trace
from aiohttp import web

from source.config import config
from source.core.session.manager import SessionManager
from source.utils.metrics import track_websocket_message
from source.utils.tracing import optional_trace_span

logger = logging.getLogger('websocket_handler_refresh')


async def handle_request_full_refresh(
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
    """Process a full refresh request from client"""
    with optional_trace_span(tracer, "handle_request_full_refresh") as span:
        span.set_attribute("client_id", client_id)
        span.set_attribute("device_id", device_id)
        span.set_attribute("compression_enabled", config.websocket.enable_compression)

        logger.info(f"Processing full refresh request for device {device_id} - compression: {'enabled' if config.websocket.enable_compression else 'disabled'}")

        # Get the WebSocket manager from session manager
        websocket_manager = kwargs.get('websocket_manager')
        
        if not config.websocket.enable_compression:
            # Compression is disabled, all messages are already full
            response = {
                'type': 'full_refresh_ack',
                'timestamp': message.get('timestamp'),
                'message': 'Compression disabled - all data is already sent uncompressed',
                'compression_status': 'disabled'
            }
        elif websocket_manager:
            # Force full refresh for this device
            await websocket_manager.force_full_refresh(device_id)
            
            response = {
                'type': 'full_refresh_ack',
                'timestamp': message.get('timestamp'),
                'message': 'Full refresh will be sent with next data update',
                'compression_status': 'enabled'
            }
        else:
            response = {
                'type': 'full_refresh_error',
                'timestamp': message.get('timestamp'),
                'message': 'WebSocket manager not available',
                'compression_status': 'error'
            }

        try:
            if not ws.closed:
                await ws.send_json(response)
                track_websocket_message("sent", "full_refresh_ack")
        except Exception as e:
            logger.error(f"Failed to send full refresh ack for device {device_id}: {e}")