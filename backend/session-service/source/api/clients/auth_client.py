"""
Authentication service client.
Handles authentication and token validation by communicating with the auth service.
"""
import logging
import json
import aiohttp
import asyncio
from typing import Dict, Any, Optional

from source.config import config
from source.utils.circuit_breaker import CircuitBreaker, CircuitOpenError

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
        try:
            # Execute request with circuit breaker
            return await self.circuit_breaker.execute(
                self._validate_token_request, token
            )
        except CircuitOpenError as e:
            logger.warning(f"Circuit open for auth service: {e}")
            return {'valid': False, 'error': 'Authentication service unavailable'}
        except Exception as e:
            logger.error(f"Error validating token: {e}")
            return {'valid': False, 'error': str(e)}
    
    async def _validate_token_request(self, token: str) -> Dict[str, Any]:
        """Make the actual validation request"""
        session = await self._get_session()
        headers = {'Authorization': f'Bearer {token}'}
        
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
                
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error validating token: {e}")
            raise
        except asyncio.TimeoutError:
            logger.error("Timeout validating token")
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