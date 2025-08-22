# source/api/utils.py
"""
Shared API utility functions for both REST and WebSocket APIs.
"""
import logging
import aiohttp
from typing import Dict, Any
from source.config import config

logger = logging.getLogger('api_utils')


async def verify_book_ownership(user_id: str, book_id: str, session_manager) -> bool:
    """Verify that user_id owns book_id"""
    try:
        pool = await session_manager.store_manager.session_store._get_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval('''
                SELECT 1 FROM fund.books
                WHERE book_id = $1 AND user_id = $2
                LIMIT 1
            ''', book_id, user_id)
            return result is not None
    except Exception as e:
        logger.error(f"Error verifying book ownership: {e}")
        return False

async def validate_token_with_auth_service(token: str, headers: dict = None) -> Dict[str, Any]:
    """
    Call the auth service directly to validate a token.

    Args:
        token: JWT token to validate
        headers: Additional headers to include

    Returns:
        Dict with validation results
    """
    auth_service_url = config.services.auth_service_url
    if headers is None:
        headers = {'Authorization': f'Bearer {token}'}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                    f'{auth_service_url}/api/auth/validate',
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_data = await response.json()
                    logger.warning(f"Auth service returned error: {error_data}")
                    return {'valid': False, 'error': error_data.get('error', 'Unknown error')}
    except Exception as e:
        logger.error(f"Error validating token with auth service: {e}")
        return {'valid': False, 'error': str(e)}
