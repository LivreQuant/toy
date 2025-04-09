# websocket/emitters/exchange_emitter.py
"""
Handles formatting and broadcasting exchange data updates.
"""
import logging
import time
from typing import Dict, Any, TYPE_CHECKING

# Assuming metrics/tracing utilities are accessible
from source.utils.metrics import track_websocket_message

# Type hint WebSocketManager to avoid circular dependency
if TYPE_CHECKING:
    from ..manager import WebSocketManager

logger = logging.getLogger('websocket_emitter_exchange')


async def send_exchange_update(
        manager: 'WebSocketManager',  # Pass manager instance for broadcasting
        *,
        session_id: str,
):
    """Formats and broadcasts the 'exchange_data_status' message."""
    payload = {
        'type': 'exchange_data_status',
        'timestamp': int(time.time() * 1000),
    }
    logger.debug(f"Broadcasting 'exchange_data_status' for session {session_id}")

    # Use the manager's broadcast utility
    await manager.broadcast_to_session(session_id, payload)

    # Track metric for sent message (might be tracked per-client in broadcast,
    # but tracking once per broadcast event here might be sufficient)
    track_websocket_message("sent_broadcast", "exchange_data_status")
