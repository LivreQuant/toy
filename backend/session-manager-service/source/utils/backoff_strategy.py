# interface/session-manager-service/source/utils/backoff_strategy.py

import random
import time
from typing import Optional

class BackoffStrategy:
    """Implements exponential backoff with jitter for reconnection attempts"""
    
    def __init__(
        self, 
        initial_backoff_ms: int = 1000, 
        max_backoff_ms: int = 30000,
        jitter_factor: float = 0.5
    ):
        """
        Initialize the backoff strategy
        
        Args:
            initial_backoff_ms: Initial backoff time in milliseconds
            max_backoff_ms: Maximum backoff time in milliseconds
            jitter_factor: Controls jitter range (0-1), with 0.5 giving ±50% jitter
        """
        self.initial_backoff_ms = initial_backoff_ms
        self.max_backoff_ms = max_backoff_ms
        self.jitter_factor = min(1.0, max(0.0, jitter_factor))
        self.attempt = 0
        
    def next_backoff_time(self) -> int:
        """
        Calculate the next backoff time with jitter
        
        Returns:
            Backoff time in milliseconds
        """
        self.attempt += 1
        
        # Calculate base backoff with exponential increase
        base_backoff = min(
            self.max_backoff_ms,
            self.initial_backoff_ms * (2 ** (self.attempt - 1))
        )
        
        # Add jitter (base_backoff * random value between (1-jitter_factor) and (1+jitter_factor))
        # e.g., with jitter_factor=0.5, this gives a range of 0.5x to 1.5x the base backoff
        jitter = 1.0 - self.jitter_factor + (random.random() * self.jitter_factor * 2)
        
        return int(base_backoff * jitter)
    
    def reset(self) -> None:
        """Reset the backoff strategy"""
        self.attempt = 0
        
    def get_current_attempt(self) -> int:
        """Get the current attempt number"""
        return self.attempt