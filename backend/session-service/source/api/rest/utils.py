# source/api/rest/utils.py
"""
REST API utility functions.
"""
import json


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
