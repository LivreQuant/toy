# source/api/auth_client.py
import logging
import aiohttp
import json
import asyncio
from typing import Dict, Any, Optional

logger = logging.getLogger('auth_client')


class AuthClient:
    """Client for communicating with auth service REST API"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = None
        self._conn_lock = asyncio.Lock()  # Lock for session initialization

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
        """Validate a JWT token"""
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
            return {'valid': False, 'error': f"Auth service unavailable: {str(e)}"}
        except asyncio.TimeoutError:
            logger.error("Timeout validating token")
            return {'valid': False, 'error': "Auth service timeout"}
        except Exception as e:
            logger.error(f"Error validating token: {e}")
            return {'valid': False, 'error': str(e)}
