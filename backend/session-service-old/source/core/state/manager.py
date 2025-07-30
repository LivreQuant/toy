"""
State manager for session service.
Simplified for single-user service.
"""
import logging
import asyncio
import time
import uuid

logger = logging.getLogger('state_manager')


class StateManager:
    """
    Manages the single session service state.
    """

    def __init__(self):
        """Initialize the state manager"""
        self._lock = asyncio.Lock()

        # Service state - for a single user service, we only need to track if ready
        self._is_ready = True
        self._session_id = None
        self._user_id = None
        self._start_time = None

    async def initialize(self):
        """Initialize the state manager at service startup"""
        async with self._lock:
            self._is_ready = True
            self._session_id = None
            self._user_id = None
            self._start_time = None
            logger.info("State manager initialized to READY state")

    async def set_active(self, user_id: str):
        """
        Mark the service as actively serving a session.

        Returns:
            True
        """
        async with self._lock:
            self._is_ready = False
            self._session_id = str(uuid.uuid4())
            self._user_id = user_id
            self._start_time = time.time()
            logger.info(f"Service state set to ACTIVE for session {self._session_id}")
            return True

    def is_ready(self):
        """Check if the service is in ready state"""
        return self._is_ready

    def is_active(self):
        """Check if the service has an active session"""
        return self._session_id is not None

    def get_active_session_id(self):
        """Get the active session ID if any"""
        return self._session_id

    def get_user_id(self):
        """Get the user id"""
        return self._user_id

    def get_uptime_seconds(self):
        """Get the time this session has been active"""
        if not self._start_time:
            return 0
        return time.time() - self._start_time

    def get_status_info(self):
        """Get detailed status information"""
        return {
            "is_ready": self._is_ready,
            "is_active": self._session_id is not None,
            "active_session_id": self._session_id,
            "active_user_id": self._user_id,
            "start_time": self._start_time,
            "uptime_seconds": self.get_uptime_seconds(),
        }

    async def close(self, keep_simulator=False):
        """
        Clean up the state manager during service shutdown.

        Args:
            keep_simulator: If True, don't stop the simulator when resetting state
        """
        async with self._lock:
            old_session = self._session_id
            # Completely clear all session-related state
            self._is_ready = True
            self._session_id = None
            self._user_id = None
            self._start_time = None
            if old_session:
                logger.info(
                    f"Session {old_session} closed, service reset to READY state. Keep simulator: {keep_simulator}")
