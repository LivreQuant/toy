import logging
import aiohttp
import time
import asyncio
from typing import Dict, Any

from source.config import config
from source.utils.circuit_breaker import CircuitBreaker, CircuitOpenError
from source.utils.metrics import track_auth_request, set_circuit_state, track_circuit_failure

logger = logging.getLogger('auth_client')

class AuthClient:
    """Client for communicating with auth service REST API"""

    def __init__(self, base_url: str = None):
        """
        Initialize the auth client
        
        Args:
            base_url: Base URL for the auth service
        """
        self.base_url = (base_url or config.auth_service_url).rstrip('/')
        self.session = None
        self._conn_lock = asyncio.Lock()  # Lock for session initialization
        
        # Create circuit breaker
        self.breaker = CircuitBreaker(
            name="auth_service",
            failure_threshold=3,
            reset_timeout_ms=30000  # 30 seconds
        )

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
        Validate a JWT token
        
        Args:
            token: JWT token to validate
            
        Returns:
            Response data containing token validity
        """
        try:
            # Update circuit state in metrics
            set_circuit_state("auth_service", self.breaker.state.name)

            # Execute with circuit breaker
            start_time = time.time()
            result = await self.breaker.execute(self._validate_token_request, token)
            duration = time.time() - start_time

            # Record metrics
            success = result.get('valid', False)
            track_auth_request("validate_token", success, duration)

            return result
        except CircuitOpenError:
            track_circuit_failure("auth_service")
            logger.warning("Auth service circuit breaker open")
            return {'valid': False, 'error': 'Auth service unavailable'}
        except Exception as e:
            logger.error(f"Error validating token: {e}")
            return {'valid': False, 'error': str(e)}

    async def _validate_token_request(self, token: str) -> Dict[str, Any]:
        """Make the actual token validation request"""
        session = await self._get_session()
        headers = {'Authorization': f'Bearer {token}'}

        try:
            # Attempt with retries for transient issues
            max_retries = 3
            retry_delay = 0.5  # Start with 0.5 second delay

            for attempt in range(max_retries):
                try:
                    async with session.post(
                            f'{self.base_url}/api/auth/validate',
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        data = await response.json()

                        if response.status != 200:
                            logger.warning(f"Token validation failed: {data.get('error', 'Unknown error')}")
                            return {'valid': False, 'error': data.get('error')}

                        return data

                except (aiohttp.ClientConnectorError, aiohttp.ServerTimeoutError) as conn_error:
                    # Only retry on connection errors, not validation errors
                    if attempt < max_retries - 1:
                        logger.warning(f"Connection error to auth service (attempt {attempt + 1}): {conn_error}")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        raise

        except aiohttp.ClientError as e:
            logger.error(f"HTTP error validating token: {e}")
            raise
        except asyncio.TimeoutError:
            logger.error("Timeout validating token")
            raise
        