"""
Authentication service client.
Handles authentication and token validation by communicating with the auth service.
"""
import logging
import time
import aiohttp
import asyncio
from opentelemetry import trace
from typing import Dict, Any, Optional

from source.config import config
from source.utils.circuit_breaker import CircuitBreaker, CircuitOpenError
from source.utils.metrics import track_external_request, track_circuit_breaker_state, track_circuit_breaker_failure
from source.utils.tracing import optional_trace_span

logger = logging.getLogger('auth_client')

class AuthClient:
    """Client for the authentication service"""
    
    def __init__(self):
        """Initialize the auth service client"""
        self.base_url = config.services.auth_service_url
        self.session = None
        self._conn_lock = asyncio.Lock()
        
        # Create circuit breaker
        self.circuit_breaker = CircuitBreaker(
            name="auth_service",
            failure_threshold=3,
            reset_timeout_ms=30000  # 30 seconds
        )

        # Register callback for circuit breaker state changes
        self.circuit_breaker.on_state_change(self._on_circuit_state_change)

        # Create tracer
        self.tracer = trace.get_tracer("auth_client")

    def _on_circuit_state_change(self, name, old_state, new_state, info):
        """Handle circuit breaker state changes"""
        logger.info(f"Circuit breaker '{name}' state change: {old_state.value} -> {new_state.value}")
        track_circuit_breaker_state("auth_service", new_state.value)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with thread safety"""
        async with self._conn_lock:
            if self.session is None or self.session.closed:
                timeout = aiohttp.ClientTimeout(total=10, connect=3)
                self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close(self):
        """Close HTTP session"""
        async with self._conn_lock:
            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None
    
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate a JWT token with the auth service
        
        Args:
            token: The JWT token to validate
            
        Returns:
            Dict with validation results
        """
        with optional_trace_span(self.tracer, "validate_token") as span:
            span.set_attribute("token_present", token is not None)

            try:
                # Execute request with circuit breaker
                return await self.circuit_breaker.execute(
                    self._validate_token_request, token
                )
            except CircuitOpenError as e:
                logger.warning(f"Circuit open for auth service: {e}")
                span.set_attribute("error", "Authentication service unavailable")
                span.set_attribute("circuit_open", True)
                return {'valid': False, 'error': 'Authentication service unavailable'}
            except Exception as e:
                logger.error(f"Error validating token: {e}")
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return {'valid': False, 'error': str(e)}
    
    async def _validate_token_request(self, token: str) -> Dict[str, Any]:
        """Make the actual validation request"""
        with optional_trace_span(self.tracer, "validate_token_request") as span:
            start_time = time.time()
            session = await self._get_session()
            headers = {'Authorization': f'Bearer {token}'}

            logger.info(f"REQUEST AUTH VALID: {self.base_url}/api/auth/validate")
            try:
                async with session.post(
                    f'{self.base_url}/api/auth/validate',
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    data = await response.json()

                    # Track external request metrics
                    duration = time.time() - start_time
                    track_external_request("auth_service", "validate_token", response.status, duration)

                    logger.info(f"RECIEVE VALIDATION: {response}")
                    
                    span.set_attribute("http.status_code", response.status)
                    span.set_attribute("token_valid", data.get('valid', False))

                    if response.status != 200:
                        error_msg = data.get('error', 'Unknown error')
                        logger.warning(f"Token validation failed: {error_msg}")
                        span.set_attribute("error", error_msg)
                        return {'valid': False, 'error': error_msg}

                    return data

            except aiohttp.ClientError as e:
                logger.error(f"HTTP error validating token: {e}")
                span.record_exception(e)
                span.set_attribute("error", str(e))
                track_circuit_breaker_failure("auth_service")
                raise
            except asyncio.TimeoutError:
                logger.error("Timeout validating token")
                span.set_attribute("error", "Request timeout")
                track_circuit_breaker_failure("auth_service")
                raise
    
    async def check_service(self) -> bool:
        """Check if auth service is available"""
        try:
            session = await self._get_session()
            async with session.get(f'{self.base_url}/health', timeout=2) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"Auth service health check failed: {e}")
            return False