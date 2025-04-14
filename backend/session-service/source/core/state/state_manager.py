"""
State manager for session service.
Simplified for single-user service.
"""
import logging
import asyncio
import time

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
        self._start_time = None

    async def initialize(self):
        """Initialize the state manager at service startup"""
        async with self._lock:
            self._is_ready = True
            self._session_id = None
            self._start_time = None
            logger.info("State manager initialized to READY state")

    async def set_ready(self):
        """Mark the service as ready"""
        async with self._lock:
            self._is_ready = True
            self._session_id = None
            logger.info("Service state set to READY")
            return True

    async def set_active(self, session_id: str):
        """
        Mark the service as actively serving a session.

        Args:
            session_id: The ID of the active session

        Returns:
            True
        """
        async with self._lock:
            self._is_ready = False
            self._session_id = session_id
            self._start_time = time.time()
            logger.info(f"Service state set to ACTIVE for session {session_id}")
            return True

    async def reset_to_ready(self):
        """
        Reset the service state back to ready.

        Returns:
            True
        """
        async with self._lock:
            old_session = self._session_id
            # Completely clear all session-related state
            self._is_ready = True
            self._session_id = None
            self._start_time = None
            
            # Additional cleanup steps
            if hasattr(self, '_active_resources'):
                # Close any active resources
                for resource in self._active_resources:
                    try:
                        await resource.close()
                    except Exception as e:
                        logger.error(f"Error closing resource during reset: {e}")
            
            logger.critical(f"SERVICE RESET: Was serving session {old_session}")
    def is_ready(self):
        """Check if the service is in ready state"""
        return self._is_ready

    def is_active(self):
        """Check if the service has an active session"""
        return self._session_id is not None

    def get_active_session_id(self):
        """Get the active session ID if any"""
        return self._session_id

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
            "start_time": self._start_time,
            "uptime_seconds": self.get_uptime_seconds(),
        }

    async def close(self):
        """Clean up the state manager during service shutdown"""
        async with self._lock:
            await self.reset_to_ready()
            logger.info("State manager closed")
