# source/api/utils.py
"""
Shared API utility functions for both REST and WebSocket APIs.
"""
import logging
import json
import aiohttp
from typing import Dict, Any
from source.config import config

logger = logging.getLogger('api_utils')


async def get_token_from_request(request):
    """
    Extract token from request headers, query parameters, or JSON body.

    Priority:
    1. Authorization: Bearer <token> header
    2. 'token' query parameter
    3. 'token' field in JSON body (if applicable)

    Args:
        request: The aiohttp web request object.

    Returns:
        The extracted token string, or None if not found.
    """
    # 1. Try Authorization header
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header[7:]

    # 2. Try query parameter
    token = request.query.get('token')
    if token:
        return token

    # 3. Try POST body (for JSON requests)
    content_type = request.headers.get('Content-Type', '')
    # Check if body exists and content type suggests JSON before attempting read/parse
    if request.can_read_body and 'application/json' in content_type:
        try:
            # Use await request.json() which handles parsing
            data = await request.json()
            if isinstance(data, dict) and 'token' in data:
                return data['token']
        except json.JSONDecodeError:
            # Ignore if body is not valid JSON
            pass
        except Exception:
            # Log other potential errors if needed, but generally ignore for token extraction
            pass  # E.g. reading body fails for some reason

    return None


async def validate_token_with_auth_service(token: str) -> Dict[str, Any]:
    """
    Call the auth service directly to validate a token.

    Args:
        token: JWT token to validate

    Returns:
        Dict with validation results
    """
    auth_service_url = config.services.auth_service_url
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
