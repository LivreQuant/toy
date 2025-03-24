import logging
import time
import asyncio
from enum import Enum
from typing import Callable, Any, Optional, List

logger = logging.getLogger('circuit_breaker')

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "CLOSED"         # Normal operation, requests go through
    OPEN = "OPEN"             # Circuit is open, fast-fails requests
    HALF_OPEN = "HALF_OPEN"   # Testing if service is healthy again

class CircuitOpenError(Exception):
    """Exception raised when a circuit is open"""
    def __init__(self, message: str, service: str, remaining_ms: int = 0):
        self.message = message
        self.service = service
        self.remaining_ms = remaining_ms
        super().__init__(self.message)

class CircuitBreaker:
    """
    Implements the circuit breaker pattern for service-to-service communication.
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        reset_timeout_ms: int = 30000,  # 30 seconds
        half_open_max_calls: int = 1,
        exclude_exceptions: List[type] = None
    ):
        """
        Initialize circuit breaker
        
        Args:
            name: Name to identify this circuit breaker
            failure_threshold: Number of consecutive failures before opening circuit
            reset_timeout_ms: Time in milliseconds to wait before trying again
            half_open_max_calls: Max number of calls in half-open state
            exclude_exceptions: Exceptions that don't count as failures
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout_ms = reset_timeout_ms
        self.half_open_max_calls = half_open_max_calls
        self.exclude_exceptions = exclude_exceptions or []
        
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.last_failure_time = 0
        self.tripped_at = 0
        self.half_open_calls = 0
        self.half_open_successes = 0
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with circuit breaker protection
        
        Args:
            func: The async function to execute
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            The result of the function call
            
        Raises:
            CircuitOpenError: If the circuit is open
            The original exception if the call fails
        """
        async with self._lock:
            # Check if circuit is open
            if self.state == CircuitState.OPEN:
                # Check if we should transition to half-open
                if time.time() * 1000 - self.tripped_at > self.reset_timeout_ms:
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                    self.half_open_successes = 0
                    logger.info(f"Circuit {self.name} transitioning from OPEN to HALF_OPEN")
                else:
                    # Circuit is open, fast-fail the request
                    remaining_ms = int(self.reset_timeout_ms - (time.time() * 1000 - self.tripped_at))
                    logger.warning(f"Circuit {self.name} is OPEN for {remaining_ms}ms more")
                    raise CircuitOpenError(
                        f"Circuit {self.name} is open", 
                        service=self.name,
                        remaining_ms=remaining_ms
                    )
            
            # Check if we've reached the limit of half-open calls
            if self.state == CircuitState.HALF_OPEN and self.half_open_calls >= self.half_open_max_calls:
                # Still in the testing period and max calls are in flight
                raise CircuitOpenError(
                    f"Circuit {self.name} is half-open and at capacity",
                    service=self.name
                )
            
            # Allow the call to proceed
            if self.state == CircuitState.HALF_OPEN:
                self.half_open_calls += 1
        
        # Execute the function outside the lock to prevent deadlocks
        try:
            # Execute the function
            result = await func(*args, **kwargs)
            
            # On success, update state
            async with self._lock:
                if self.state == CircuitState.HALF_OPEN:
                    self.half_open_calls -= 1
                    self.half_open_successes += 1
                    
                    # If we've had enough successes, close the circuit
                    if self.half_open_successes >= 1:  # Just need 1 success for now
                        self.reset()
                        logger.info(f"Circuit {self.name} test call succeeded, closing circuit")
                elif self.state == CircuitState.CLOSED:
                    # Reset consecutive failures on success
                    self.consecutive_failures = 0
                    
            return result
            
        except Exception as e:
            # Check if this exception should be counted as a failure
            is_excluded = any(isinstance(e, exc_type) for exc_type in self.exclude_exceptions)
            
            if not is_excluded:
                async with self._lock:
                    # Record failure
                    self.consecutive_failures += 1
                    self.last_failure_time = int(time.time() * 1000)
                    
                    # Check if we should trip the circuit
                    if self.state == CircuitState.CLOSED and self.consecutive_failures >= self.failure_threshold:
                        self.trip()
                        logger.warning(
                            f"Circuit {self.name} tripped after {self.consecutive_failures} consecutive failures"
                        )
                    elif self.state == CircuitState.HALF_OPEN:
                        # Failure during half-open means reopen the circuit
                        self.trip()
                        logger.warning(f"Circuit {self.name} test call failed, reopening circuit")
            
            # Re-raise the original exception
            raise
    
    def trip(self) -> None:
        """Trip the circuit breaker (transition to OPEN state)"""
        self.state = CircuitState.OPEN
        self.tripped_at = int(time.time() * 1000)
    
    def reset(self) -> None:
        """Reset the circuit breaker to CLOSED state"""
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.half_open_calls = 0
        self.half_open_successes = 0