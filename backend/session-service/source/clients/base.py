# source/clients/base_client.py
"""Base client class with standardized circuit breaker functionality."""
import logging
from typing import Any, Callable
from opentelemetry import trace

from source.utils.circuit_breaker import CircuitBreaker, CircuitOpenError
from source.utils.metrics import track_circuit_breaker_state, track_circuit_breaker_failure

logger = logging.getLogger('base_client')


class BaseClient:
    """Base client with circuit breaker functionality."""

    def __init__(self, service_name: str,
                 failure_threshold: int = 3,
                 reset_timeout_ms: int = 30000):
        """
        Initialize the base client.

        Args:
            service_name: Name of the service for circuit breaker and metrics
            failure_threshold: Number of failures before opening circuit
            reset_timeout_ms: Time to wait before testing circuit again
        """
        self.service_name = service_name
        self.tracer = trace.get_tracer(f"{service_name}_client")

        # Create circuit breaker
        self.circuit_breaker = CircuitBreaker(
            name=service_name,
            failure_threshold=failure_threshold,
            reset_timeout_ms=reset_timeout_ms
        )

        # Register callback for circuit breaker state changes
        self.circuit_breaker.on_state_change(self._on_circuit_state_change)

    def _on_circuit_state_change(self, name, old_state, new_state, info=None):
        """Handle circuit breaker state changes."""
        logger.info(f"Circuit breaker '{name}' state change: {old_state.value} -> {new_state.value}")
        track_circuit_breaker_state(self.service_name, new_state.value)

    async def execute_with_cb(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with circuit breaker protection.

        Args:
            func: The function to execute
            args, kwargs: Arguments to pass to the function

        Returns:
            The result of the function

        Raises:
            CircuitOpenError: If circuit is open
        """
        try:
            return await self.circuit_breaker.execute(func, *args, **kwargs)
        except CircuitOpenError as e:
            logger.warning(f"Circuit open for {self.service_name}: {e}")
            track_circuit_breaker_failure(self.service_name)
            raise

    async def close(self):
        """Close any resources. Override in subclasses."""
        pass

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
