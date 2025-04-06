# source/api/clients/session_client.py
import logging
import aiohttp
import asyncio
import time
from typing import Dict, Any, Optional

from source.config import config
from source.utils.circuit_breaker import CircuitBreaker, CircuitOpenError
from source.utils.metrics import track_session_request, set_circuit_state, track_circuit_failure
from opentelemetry import trace

from source.utils.tracing import optional_trace_span

logger = logging.getLogger('session_client')


class SessionClient:
    """Client for communicating with session service REST API"""

    def __init__(self, base_url: str):
        """
        Initialize the session client

        Args:
            base_url: Base URL for the session service
        """
        self.base_url = base_url.rstrip('/')
        self.session = None
        self._conn_lock = asyncio.Lock()
        self.tracer = trace.get_tracer("session_client")

        # Create circuit breaker
        self.breaker = CircuitBreaker(
            name="session_service",
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

    async def get_session_info(self, session_id: str, token: str) -> Dict[str, Any]:
        """
        Get session information from the session service

        Args:
            session_id: The session ID
            token: Authentication token

        Returns:
            Session details including simulator information
        """
        with optional_trace_span(self.tracer, "get_session_info") as span:
            span.set_attribute("session_id", session_id)

            try:
                # Update circuit state in metrics
                set_circuit_state("session_service", self.breaker.state.name)

                # Execute with circuit breaker
                start_time = time.time()
                result = await self.breaker.execute(
                    self._get_session_info_request, session_id, token
                )
                duration = time.time() - start_time

                # Record metrics
                success = result.get('success', False)
                track_session_request("get_session_info", success, duration)

                span.set_attribute("success", success)
                if not success:
                    span.set_attribute("error", result.get('error', 'Unknown error'))

                return result
            except CircuitOpenError:
                track_circuit_failure("session_service")
                span.set_attribute("circuit_open", True)
                span.set_attribute("success", False)
                logger.warning("Session service circuit breaker open")
                return {
                    'success': False,
                    'error': 'Session service unavailable'
                }
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("success", False)
                logger.error(f"Error getting session info: {e}")
                return {'success': False, 'error': str(e)}

    async def _get_session_info_request(self, session_id: str, token: str) -> Dict[str, Any]:
        """Make the actual session info request"""
        with optional_trace_span(self.tracer, "_get_session_info_request") as span:
            span.set_attribute("endpoint", f"{self.base_url}/api/sessions/{session_id}")

            session = await self._get_session()
            headers = {'Authorization': f'Bearer {token}'}

            try:
                async with session.get(
                        f'{self.base_url}/api/sessions/{session_id}',
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    span.set_attribute("http.status_code", response.status)
                    data = await response.json()

                    if response.status != 200:
                        logger.warning(f"Session info request failed: {data.get('error', 'Unknown error')}")
                        span.set_attribute("error", data.get('error', 'Unknown error'))
                        return {'success': False, 'error': data.get('error')}

                    span.set_attribute("success", True)
                    return data

            except aiohttp.ClientError as e:
                logger.error(f"HTTP error getting session info: {e}")
                span.record_exception(e)
                span.set_attribute("error", str(e))
                raise
            except asyncio.TimeoutError:
                logger.error("Timeout getting session info")
                span.set_attribute("error", "Timeout")
                raise

    async def check_service(self) -> bool:
        """Check if session service is available"""
        with optional_trace_span(self.tracer, "check_service") as span:
            try:
                session = await self._get_session()
                async with session.get(f'{self.base_url}/health', timeout=2) as response:
                    span.set_attribute("http.status_code", response.status)
                    span.set_attribute("success", response.status == 200)
                    return response.status == 200
            except Exception as e:
                logger.error(f"Session service health check failed: {e}")
                span.record_exception(e)
                span.set_attribute("success", False)
                return False
