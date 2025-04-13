"""
State manager for session service.
Controls the service's readiness state to handle user sessions.
"""
import logging
import asyncio
import time
from typing import Optional

logger = logging.getLogger('state_manager')


class StateManager:
    """
    Manages the session service state (ready, active, resetting).
    Controls whether the instance can accept new users.
    """

    def __init__(self):
        """Initialize the state manager"""
        self._lock = asyncio.Lock()

        # Service state
        self._is_ready = True
        self._active_user_id = None
        self._active_session_id = None
        self._connection_time = None

    async def initialize(self):
        """Initialize the state manager at service startup"""
        async with self._lock:
            self._is_ready = True  # Start as ready
            self._active_user_id = None
            self._active_session_id = None
            self._connection_time = None
            logger.info("State manager initialized to READY state")

    async def set_ready(self):
        """Mark the service as ready to receive a new user"""
        async with self._lock:
            self._is_ready = True
            self._active_user_id = None
            self._active_session_id = None
            self._connection_time = None
            logger.info("Service state set to READY")
            return True

    async def set_active(self, user_id: str, session_id: str) -> bool:
        """
        Mark the service as actively serving a user.

        Args:
            user_id: The ID of the active user
            session_id: The ID of the active session

        Returns:
            True if successfully set to active, False otherwise
        """
        async with self._lock:
            if self._active_user_id is not None:
                logger.warning(f"Attempted to set active but user {self._active_user_id} is already active")
                return False

            self._is_ready = False
            self._active_user_id = user_id
            self._active_session_id = session_id
            self._connection_time = time.time()

            logger.info(f"Service state set to ACTIVE for user {user_id}, session {session_id}")
            return True

    async def reset_to_ready(self) -> bool:
        """
        Reset the service state back to ready after a user disconnects.

        Returns:
            True if successfully reset, False otherwise
        """
        async with self._lock:
            # Reset all state variables
            old_user_id = self._active_user_id
            self._is_ready = True
            self._active_user_id = None
            self._active_session_id = None
            self._connection_time = None

            logger.info(f"Service state reset to READY (was active for user {old_user_id})")
            return True

    def is_ready(self) -> bool:
        """Check if the service is in ready state"""
        return self._is_ready

    def is_active(self) -> bool:
        """Check if the service has an active user"""
        return self._active_user_id is not None

    def get_active_user_id(self) -> Optional[str]:
        """Get the active user ID if any"""
        return self._active_user_id

    def get_active_session_id(self) -> Optional[str]:
        """Get the active session ID if any"""
        return self._active_session_id

    def get_active_connection_time(self) -> Optional[float]:
        """Get the timestamp when the active connection was established"""
        return self._connection_time

    def get_status_info(self) -> dict:
        """Get detailed status information"""
        current_time = time.time()
        connection_duration = None
        if self._connection_time:
            connection_duration = current_time - self._connection_time

        return {
            "is_ready": self._is_ready,
            "is_active": self._active_user_id is not None,
            "active_user_id": self._active_user_id,
            "active_session_id": self._active_session_id,
            "connection_time": self._connection_time,
            "connection_duration_seconds": connection_duration,
        }

    async def close(self):
        """Clean up the state manager during service shutdown"""
        async with self._lock:
            await self.reset_to_ready()
            logger.info("State manager closed")
