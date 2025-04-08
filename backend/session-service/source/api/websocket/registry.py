# websocket/registry.py
"""
Manages the state of active WebSocket connections for a single server instance.
Handles registration, unregistration, and provides access to connection info.
"""
import logging
import time
from typing import Dict, Set, Any, Optional, Tuple, ItemsView, List

from aiohttp import web

# Assuming SessionManager has db_manager, or pass db_manager directly
# Adjust import path as needed
from source.core.session_manager import SessionManager
from source.utils.metrics import track_websocket_connection_count

logger = logging.getLogger('websocket_registry')

class WebSocketRegistry:
    """Stores and manages active WebSocket connections and their metadata."""

    def __init__(self, session_manager: SessionManager):
        """
        Initialize the registry.

        Args:
            session_manager: The session manager instance (used to access db_manager).
        """
        # session_id -> set of ws connections for that session
        self._connections: Dict[str, Set[web.WebSocketResponse]] = {}
        # ws -> connection metadata dictionary
        self._connection_info: Dict[web.WebSocketResponse, Dict[str, Any]] = {}
        # Store db_manager for convenience
        self._db_manager = session_manager.db_manager # Assuming this path exists

        logger.info("WebSocketRegistry initialized.")

    async def register(
        self,
        ws: web.WebSocketResponse,
        *,
        session_id: str,
        user_id: Any,
        client_id: str,
        device_id: str
    ) -> bool:
        """
        Register a new WebSocket connection.

        Args:
            ws: The WebSocket connection object.
            session_id: Associated session ID.
            user_id: Associated user ID.
            client_id: Client's unique ID for this connection.
            device_id: Client's device ID.

        Returns:
            True if registration was successful, False otherwise (e.g., already registered).
        """
        if ws in self._connection_info:
            logger.warning(f"Attempted to register already registered WebSocket: client={client_id}, session={session_id}")
            return False

        # Add to session -> ws mapping
        if session_id not in self._connections:
            self._connections[session_id] = set()
        self._connections[session_id].add(ws)

        # Store connection metadata
        self._connection_info[ws] = {
            'session_id': session_id,
            'user_id': user_id,
            'client_id': client_id,
            'device_id': device_id,
            'connected_at': time.time(),
            'last_activity': time.time()
        }

        # Update session metadata in DB
        # Run this as a background task to avoid blocking registration? For now, await.
        try:
            await self._db_manager.update_session_metadata(session_id, {
                'device_id': device_id, # Update device ID on new connection potentially
                'frontend_connections': len(self._connections[session_id]),
                'last_ws_connection': time.time()
            })
        except Exception as e:
            logger.error(f"Failed to update session metadata during registration for session {session_id}: {e}", exc_info=True)
            # Should we rollback registration? For now, proceed.

        # Update global connection count metric
        total_connections = self.get_total_connection_count()
        track_websocket_connection_count(total_connections)

        logger.info(f"WebSocket registered: session={session_id}, client={client_id}, device={device_id}. Total={total_connections}")
        return True

    async def unregister(self, ws: web.WebSocketResponse) -> Tuple[Optional[str], Optional[str], bool]:
        """
        Unregister a WebSocket connection.

        Args:
            ws: The WebSocket connection object.

        Returns:
            A tuple: (session_id, client_id, session_became_empty)
            Returns (None, None, False) if ws was not found.
        """
        conn_info = self._connection_info.pop(ws, None)
        if not conn_info:
            # Not registered or already unregistered
            # logger.debug(f"Attempted to unregister a non-registered WebSocket.")
            return None, None, False

        session_id = conn_info['session_id']
        client_id = conn_info['client_id']
        session_became_empty = False

        # Remove from session -> ws mapping
        if session_id in self._connections:
            self._connections[session_id].discard(ws)
            session_connection_count = len(self._connections[session_id])

            if session_connection_count == 0:
                # Last connection for this session closed
                del self._connections[session_id]
                session_became_empty = True
                logger.info(f"Last WebSocket connection closed for session {session_id}.")
        else:
            # Should not happen if conn_info was found, but handle defensively
            logger.warning(f"Session {session_id} not found in _connections during unregister for client {client_id}.")
            session_connection_count = 0
            session_became_empty = True # Assume empty if session key doesn't exist

        # Update session metadata in DB
        try:
            await self._db_manager.update_session_metadata(session_id, {
                'frontend_connections': session_connection_count,
                'last_ws_disconnection': time.time()
            })
        except Exception as e:
             logger.error(f"Failed to update session metadata during unregistration for session {session_id}: {e}", exc_info=True)

        # Update global connection count metric
        total_connections = self.get_total_connection_count()
        track_websocket_connection_count(total_connections)

        logger.info(f"WebSocket unregistered: session={session_id}, client={client_id}. Total={total_connections}. Session empty={session_became_empty}")
        return session_id, client_id, session_became_empty

    def get_connection_info(self, ws: web.WebSocketResponse) -> Optional[Dict[str, Any]]:
        """Return the metadata for a specific WebSocket connection."""
        return self._connection_info.get(ws)

    def update_connection_activity(self, ws: web.WebSocketResponse):
        """Update the 'last_activity' timestamp for a connection."""
        conn_info = self._connection_info.get(ws)
        if conn_info:
            conn_info['last_activity'] = time.time()
        # else:
            # logger.warning("Attempted to update activity for non-registered WebSocket.")

    def get_session_connections(self, session_id: str) -> Set[web.WebSocketResponse]:
        """Return the set of WebSocket connections for a given session ID."""
        return self._connections.get(session_id, set()) # Return copy or original? Return original for now.

    def get_all_connection_info_items(self) -> ItemsView[web.WebSocketResponse, Dict[str, Any]]:
        """
        Return an items view of the connection info dictionary.
        Used for iterating (e.g., by cleanup task). Be cautious if modifying during iteration.
        """
        return self._connection_info.items()

    def get_all_websockets(self) -> List[web.WebSocketResponse]:
        """Return a list of all currently registered WebSocket objects."""
        # Creates a new list, safe for iteration if registry changes
        return list(self._connection_info.keys())

    def get_total_connection_count(self) -> int:
        """Return the total number of active WebSocket connections."""
        # Simply return the size of the info map
        return len(self._connection_info)

    def clear(self):
        """Clear all registered connections. Used during shutdown."""
        self._connections.clear()
        self._connection_info.clear()
        logger.info("WebSocketRegistry cleared.")
        # Update metrics after clearing
        track_websocket_connection_count(0)