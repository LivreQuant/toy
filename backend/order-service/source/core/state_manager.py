import asyncio
import time
from enum import Enum


class ServiceState(Enum):
    READY = "READY"
    BUSY = "BUSY"
    ERROR = "ERROR"


class StateManager:
    def __init__(self, timeout_seconds=30):
        self._lock = asyncio.Lock()
        self._state = ServiceState.READY
        self._current_user_id = None
        self._state_start_time = None
        self._timeout_seconds = timeout_seconds

    async def acquire(self, user_id: str) -> bool:
        """
        Attempt to acquire the service for a specific user
        
        Args:
            user_id: User attempting to use the service
        
        Returns:
            True if service was successfully acquired, False otherwise
        """
        async with self._lock:
            # Check if service is already in use
            if self._state == ServiceState.BUSY:
                # Check if current operation has timed out
                if time.time() - self._state_start_time > self._timeout_seconds:
                    # Force release if timed out
                    await self.release()
                else:
                    return False

            # Acquire the service
            self._state = ServiceState.BUSY
            self._current_user_id = user_id
            self._state_start_time = time.time()
            return True

    async def release(self, user_id: str = None):
        """
        Release the service, optionally checking the user
        
        Args:
            user_id: Optional user ID to verify before releasing
        """
        async with self._lock:
            # If a specific user is provided, only that user can release
            if user_id and self._current_user_id != user_id:
                raise ValueError("Unauthorized service release attempt")

            # Reset state
            self._state = ServiceState.READY
            self._current_user_id = None
            self._state_start_time = None

    def is_ready(self) -> bool:
        """Check if service is ready"""
        return self._state == ServiceState.READY

    async def with_lock(self, user_id: str, operation):
        """
        Context manager for acquiring and releasing service lock
        
        Args:
            user_id: User performing the operation
            operation: Async function to execute
        
        Returns:
            Result of the operation
        """
        try:
            # Attempt to acquire lock
            acquired = await self.acquire(user_id)
            if not acquired:
                raise RuntimeError("Service is currently busy. Please try again later.")

            # Execute the operation
            return await operation()
        finally:
            # Always attempt to release, even if operation fails
            await self.release(user_id)
