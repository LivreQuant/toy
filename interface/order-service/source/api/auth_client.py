# source/api/auth_client.py
import logging
import aiohttp
import json
from typing import Dict, Any, Optional

logger = logging.getLogger('auth_client')

class AuthClient:
    """Client for communicating with auth service REST API"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
    
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """Validate a JWT token"""
        session = await self._get_session()
        headers = {'Authorization': f'Bearer {token}'}
        
        try:
            async with session.post(
                f'{self.base_url}/api/auth/validate', 
                headers=headers
            ) as response:
                data = await response.json()
                
                if response.status != 200:
                    logger.warning(f"Token validation failed: {data.get('error', 'Unknown error')}")
                    return {'valid': False, 'error': data.get('error')}
                
                return data
        except Exception as e:
            logger.error(f"Error validating token: {e}")
            return {'valid': False, 'error': str(e)}