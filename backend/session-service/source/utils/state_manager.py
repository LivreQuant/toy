"""
State manager for session service.
Controls the service's readiness state to handle user sessions.
"""
import logging
import asyncio
import time
from typing import Optional
from pathlib import Path

from source.config import Config

logger = logging.getLogger('state_manager')


class StateManager:
    """
    Manages the session service state (ready, active, resetting).
    Controls whether the instance can accept new users.
    """

    def __init__(self):
        """Initialize the state manager"""
        self.ready_file_path = Path(Config.state_management.ready_file_path)
        self.active_lock_file_path = Path(Config.state_management.active_lock_file_path)
        self._lock = asyncio.Lock()
        
        # Service state
        self._has_active_user = False
        self._is_ready = False
        self._user_id = None
        self._session_id = None
        self._connection_time = None

    async def initialize(self):
        """Initialize the state manager at service startup"""
        async with self._lock:
            if Config.state_management.reset_on_startup:
                # Remove any existing ready or active files
                self._remove_state_files()
            
            # Check if ready file already exists
            if self.ready_file_path.exists():
                self._is_ready = True
                logger.info("Service is starting in READY state (ready file exists)")
            else:
                # Create ready file to indicate service is available
                await self.set_ready()
                logger.info("Service initialized to READY state")

    async def set_ready(self):
        """Mark the service as ready to receive a new user"""
        async with self._lock:
            # Create the ready file
            try:
                self.ready_file_path.parent.mkdir(exist_ok=True, parents=True)
                self.ready_file_path.touch()
                self._is_ready = True
                self._has_active_user = False
                self._user_id = None
                self._session_id = None
                self._connection_time = None
                logger.info("Service state set to READY")
                return True
            except Exception as e:
                logger.error(f"Failed to set service to ready state: {e}")
                return False

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
            if self._has_active_user:
                logger.warning(f"Attempted to set active but user {self._user_id} is already active")
                return False
                
            try:
                # Create the active lock file
                self.active_lock_file_path.parent.mkdir(exist_ok=True, parents=True)
                with self.active_lock_file_path.open('w') as f:
                    f.write(f"{user_id}:{session_id}:{int(time.time())}")
                
                # Remove the ready file to prevent new connections
                if self.ready_file_path.exists():
                    self.ready_file_path.unlink()
                
                self._has_active_user = True
                self._is_ready = False
                self._user_id = user_id
                self._session_id = session_id
                self._connection_time = time.time()
                
                logger.info(f"Service state set to ACTIVE for user {user_id}, session {session_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to set service to active state: {e}")
                return False

    async def reset_to_ready(self) -> bool:
        """
        Reset the service state back to ready after a user disconnects.
        
        Returns:
            True if successfully reset, False otherwise
        """
        async with self._lock:
            if not self._has_active_user:
                logger.warning("Attempted to reset service state but no active user")
                # Still proceed with reset as a safety measure
            
            try:
                # Remove the active lock file
                if self.active_lock_file_path.exists():
                    self.active_lock_file_path.unlink()
                
                # Create the ready file
                result = await self.set_ready()
                
                if result:
                    logger.info("Service state reset to READY")
                return result
            except Exception as e:
                logger.error(f"Failed to reset service state: {e}")
                return False

    def _remove_state_files(self):
        """Remove ready and active files if they exist"""
        try:
            if self.ready_file_path.exists():
                self.ready_file_path.unlink()
                logger.debug("Removed ready file")
                
            if self.active_lock_file_path.exists():
                self.active_lock_file_path.unlink()
                logger.debug("Removed active lock file")
        except Exception as e:
            logger.error(f"Error removing state files: {e}")

    def is_ready(self) -> bool:
        """Check if the service is in ready state"""
        return self._is_ready and self.ready_file_path.exists()

    def is_active(self) -> bool:
        """Check if the service has an active user"""
        return self._has_active_user and self.active_lock_file_path.exists()

    def get_active_user_id(self) -> Optional[str]:
        """Get the active user ID if any"""
        return self._user_id if self._has_active_user else None

    def get_active_session_id(self) -> Optional[str]:
        """Get the active session ID if any"""
        return self._session_id if self._has_active_user else None

    def get_active_connection_time(self) -> Optional[float]:
        """Get the timestamp when the active connection was established"""
        return self._connection_time if self._has_active_user else None

    def get_status_info(self) -> dict:
        """Get detailed status information"""
        return {
            "is_ready": self.is_ready(),
            "is_active": self.is_active(),
            "active_user_id": self._user_id,
            "active_session_id": self._session_id,
            "connection_time": self._connection_time,
            "connection_duration_seconds": time.time() - self._connection_time if self._connection_time else None,
            "ready_file_exists": self.ready_file_path.exists(),
            "active_lock_file_exists": self.active_lock_file_path.exists()
        }

    async def close(self):
        """Clean up the state manager during service shutdown"""
        async with self._lock:
            self._remove_state_files()
            logger.info("State manager closed")
            