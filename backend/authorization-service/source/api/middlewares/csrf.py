# source/api/middlewares/csrf.py
import logging
from aiohttp import web

logger = logging.getLogger('csrf')

class CsrfProtection:
    """
    CSRF protection middleware for aiohttp
    Validates CSRF tokens for mutating operations
    """
    def __init__(self):
        # Define paths that require CSRF protection (POST, PUT, DELETE)
        self.protected_methods = ['POST', 'PUT', 'DELETE', 'PATCH']
        # Define paths that are exempt from CSRF protection
        self.exempt_paths = [
            '/api/auth/login',
            '/api/auth/signup',
            '/api/auth/refresh',
            '/api/auth/verify-email',
            '/api/auth/resend-verification',
            '/api/auth/forgot-username',
            '/api/auth/forgot-password',
            '/api/auth/reset-password',
            '/health',
            '/readiness',
            '/metrics'
        ]

    @web.middleware
    async def middleware(self, request, handler):
        """
        aiohttp middleware that applies CSRF protection
        """
        # Skip for exempt paths and non-protected methods
        if request.path in self.exempt_paths or request.method not in self.protected_methods:
            return await handler(request)
        
        # Get the CSRF token from the header
        csrf_token = request.headers.get('X-CSRF-Token')
        
        # Get the authentication token
        auth_header = request.headers.get('Authorization')
        
        # If this is an authenticated request that needs CSRF protection
        if auth_header and auth_header.startswith('Bearer '):
            if not csrf_token:
                logger.warning(f"Missing CSRF token for {request.method} {request.path}")
                return web.json_response({
                    'success': False, 
                    'error': 'CSRF token missing'
                }, status=403)
            
            # Validate the token (in a real implementation, you would verify against a stored token)
            # Here we're just checking it exists and has a minimum length
            if len(csrf_token) < 32:
                logger.warning(f"Invalid CSRF token for {request.method} {request.path}")
                return web.json_response({
                    'success': False, 
                    'error': 'Invalid CSRF token'
                }, status=403)
        
        return await handler(request)