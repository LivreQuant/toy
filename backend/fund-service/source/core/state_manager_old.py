# source/core/state_manager.py
import asyncio
import time
import logging
from enum import Enum

from source.db.state_repository import StateRepository

logger = logging.getLogger('state_manager')


class ServiceState(Enum):
    READY = "READY"
    BUSY = "BUSY"
    ERROR = "ERROR"


class StateManager:
    def __init__(self,
                 state_repository: StateRepository,
                 timeout_seconds=30):
        self.state_repository = state_repository
        self._lock = asyncio.Lock()
        self._state = ServiceState.READY
        self._state_start_time = None
        self._timeout_seconds = timeout_seconds
        
    async def acquire(self) -> bool:
        """
        Attempt to acquire the service

        Returns:
            True if service was successfully acquired, False otherwise
        """
        async with self._lock:
            # Check if service is already in use
            if self._state == ServiceState.BUSY:
                # Check if current operation has timed out
                if self._state_start_time and time.time() - self._state_start_time > self._timeout_seconds:
                    # Force release if timed out
                    self._state = ServiceState.READY
                    self._state_start_time = None
                    logger.warning("Forced release of timed-out service lock")
                else:
                    return False

            # Acquire the service
            self._state = ServiceState.BUSY
            self._state_start_time = time.time()
            return True

    async def release(self):
        """Release the service"""
        async with self._lock:
            # Reset state
            self._state = ServiceState.READY
            self._state_start_time = None

    def is_ready(self) -> bool:
        """Check if service is ready"""
        return self._state == ServiceState.READY

    async def with_lock(self, operation):
        """
        Execute an operation with a service lock

        Args:
            operation: Async function to execute

        Returns:
            Result of the operation

        Raises:
            RuntimeError: If the service cannot be acquired
        """
        acquired = await self.acquire()
        if not acquired:
            raise RuntimeError("Service is currently busy. Please try again later.")

        try:
            # Execute the operation
            return await operation()
        finally:
            # Always attempt to release, even if operation fails
            await self.release()

    async def validate_connection(self) -> bool:
        """
        Validate database connection for health checks
        Returns True if database is accessible, False otherwise
        """
        try:
            return await self.state_repository.check_connection()
        except Exception as e:
            logger.warning(f"Database validation failed: {e}")
            return False