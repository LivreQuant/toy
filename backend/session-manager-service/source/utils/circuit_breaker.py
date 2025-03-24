# interface/session-manager-service/source/utils/circuit_breaker.py

import time
import logging
from enum import Enum
from typing import Callable, Any, Optional, Dict

logger = logging.getLogger('circuit_breaker')

class CircuitState(Enum):
    """Enum for circuit breaker states"""
    CLOSED = "CLOSED"         # Normal operation, requests go through
    OPEN = "OPEN"             # Circuit is open, fast-fails requests
    HALF_OPEN = "HALF_OPEN"   # Testing if service is healthy again
    
class CircuitBreaker:
    """
    Implements the circuit breaker pattern for service-to-service communication.
    Tracks failures and temporarily disables calls to failing services to prevent
    cascading failures and allow recovery.
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        reset_timeout_ms: int = 60000,
        half_open_max_calls: int = 1
    ):
        """
        Initialize a new circuit breaker
        
        Args:
            name: Name to identify this circuit breaker
            failure_threshold: Number of consecutive failures before opening circuit
            reset_timeout_ms: Time in milliseconds to wait before trying again (half-open)
            half_open_max_calls: Max number of calls to allow in half-open state
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout_ms = reset_timeout_ms
        self.half_open_max_calls = half_open_max_calls
        
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.last_failure_time = 0
        self.tripped_at = 0
        self.half_open_calls = 0
    
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
        # Check if circuit is open
        if self.state == CircuitState.OPEN:
            # Check if we should transition to half-open
            if time.time() * 1000 - self.tripped_at > self.reset_timeout_ms:
                logger.info(f"Circuit {self.name} transitioning from OPEN to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
            else:
                # Circuit is open, fast-fail the request
                remaining_ms = int(self.reset_timeout_ms - (time.time() * 1000 - self.tripped_at))
                logger.warning(f"Circuit {self.name} is OPEN for {remaining_ms}ms more")
                raise CircuitOpenError(f"Circuit {self.name} is open", remaining_ms=remaining_ms)
        
        # Check if we've reached the limit of half-open calls
        if self.state == CircuitState.HALF_OPEN and self.half_open_calls >= self.half_open_max_calls:
            # Still in the testing period and max calls are in flight
            raise CircuitOpenError(f"Circuit {self.name} is half-open and at capacity")
        
        # Allow the call to proceed
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1
            
        try:
            # Execute the function
            result = await func(*args, **kwargs)
            
            # On success, reset if needed
            if self.state == CircuitState.HALF_OPEN:
                logger.info(f"Circuit {self.name} test call succeeded, closing circuit")
                self.reset()
            elif self.state == CircuitState.CLOSED:
                # Reset consecutive failures on success
                self.consecutive_failures = 0
                
            return result
            
        except Exception as e:
            # Record failure
            self.consecutive_failures += 1
            self.last_failure_time = int(time.time() * 1000)
            
            # Check if we should trip the circuit
            if self.state == CircuitState.CLOSED and self.consecutive_failures >= self.failure_threshold:
                logger.warning(
                    f"Circuit {self.name} tripped after {self.consecutive_failures} consecutive failures"
                )
                self.trip()
            elif self.state == CircuitState.HALF_OPEN:
                # Failure during half-open means reopen the circuit
                logger.warning(f"Circuit {self.name} test call failed, reopening circuit")
                self.trip()
            
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
    
    def get_state(self) -> Dict[str, Any]:
        """Get the current state of the circuit breaker"""
        return {
            "name": self.name,
            "state": self.state.value,
            "consecutive_failures": self.consecutive_failures,
            "tripped_at": self.tripped_at,
            "reset_timeout_ms": self.reset_timeout_ms,
            "time_remaining_ms": max(0, self.reset_timeout_ms - (int(time.time() * 1000) - self.tripped_at)) 
                                if self.state == CircuitState.OPEN else 0
        }

class CircuitOpenError(Exception):
    """Exception raised when a circuit is open"""
    
    def __init__(self, message: str, remaining_ms: int = 0):
        self.message = message
        self.remaining_ms = remaining_ms
        super().__init__(self.message)