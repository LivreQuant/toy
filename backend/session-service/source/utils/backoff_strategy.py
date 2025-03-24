"""
Backoff strategy for retry logic.
Implements exponential backoff with jitter to prevent thundering herd problems.
"""
import random
import time
from typing import Optional

class BackoffStrategy:
    """Implements exponential backoff with jitter for reconnection attempts"""
    
    def __init__(
        self, 
        initial_backoff_ms: int = 1000, 
        max_backoff_ms: int = 30000,
        jitter_factor: float = 0.5,
        max_retries: Optional[int] = None
    ):
        """
        Initialize the backoff strategy
        
        Args:
            initial_backoff_ms: Initial backoff time in milliseconds
            max_backoff_ms: Maximum backoff time in milliseconds
            jitter_factor: Controls jitter range (0-1)
            max_retries: Maximum number of retries (None for unlimited)
        """
        self.initial_backoff_ms = initial_backoff_ms
        self.max_backoff_ms = max_backoff_ms
        self.jitter_factor = min(1.0, max(0.0, jitter_factor))
        self.max_retries = max_retries
        self.attempt = 0
        
    def next_backoff_time(self) -> int:
        """
        Calculate the next backoff time with jitter
        
        Returns:
            Backoff time in milliseconds
        """
        self.attempt += 1
        
        # Check if max retries reached
        if self.max_retries is not None and self.attempt > self.max_retries:
            return -1  # Indicate we've exceeded max retries
        
        # Calculate base backoff with exponential increase
        base_backoff = min(
            self.max_backoff_ms,
            self.initial_backoff_ms * (2 ** (self.attempt - 1))
        )
        
        # Add jitter
        jitter = 1.0 - self.jitter_factor + (random.random() * self.jitter_factor * 2)
        
        return int(base_backoff * jitter)
    
    def reset(self) -> None:
        """Reset the backoff strategy"""
        self.attempt = 0
        
    def get_current_attempt(self) -> int:
        """Get the current attempt number"""
        return self.attempt
    
    def should_retry(self) -> bool:
        """Check if we should retry based on max retries"""
        if self.max_retries is None:
            return True
        return self.attempt < self.max_retries