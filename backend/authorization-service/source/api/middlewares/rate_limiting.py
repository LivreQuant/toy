# source/api/middlewares/rate_limiting.py
import time
import asyncio
import logging
from aiohttp import web
from collections import defaultdict

logger = logging.getLogger('rate_limiting')

class RateLimiter:
    """
    Rate limiting middleware for aiohttp
    Uses IP address and endpoint for rate limiting
    Supports different limits for different endpoints
    """
    def __init__(self):
        self.ip_requests = defaultdict(list)
        self.endpoint_limits = {
            # Public endpoints with strict limits
            '/api/auth/login': {'rate': 5, 'per': 60},  # 5 attempts per minute
            '/api/auth/signup': {'rate': 3, 'per': 60},  # 3 attempts per minute
            '/api/auth/forgot-username': {'rate': 3, 'per': 60},
            '/api/auth/forgot-password': {'rate': 3, 'per': 60},
            '/api/auth/reset-password': {'rate': 3, 'per': 60},
            '/api/auth/verify-email': {'rate': 5, 'per': 60},
            '/api/auth/resend-verification': {'rate': 2, 'per': 60},
            
            # Default limit for other endpoints
            'default': {'rate': 30, 'per': 60}  # 30 requests per minute
        }
        
        # Start cleanup task
        asyncio.create_task(self._cleanup_task())

    async def _cleanup_task(self):
        """Periodically clean up expired requests to prevent memory leaks"""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                self._cleanup()
            except Exception as e:
                logger.error(f"Error in rate limiter cleanup: {e}")

    def _cleanup(self):
        """Remove requests older than the longest time window"""
        now = time.time()
        # Find the longest time window
        max_window = max(limit['per'] for limit in self.endpoint_limits.values())
        
        # Clean up expired entries
        for ip in list(self.ip_requests.keys()):
            self.ip_requests[ip] = [t for t in self.ip_requests[ip] if now - t < max_window]
            if not self.ip_requests[ip]:
                del self.ip_requests[ip]

    def _is_rate_limited(self, ip, endpoint):
        """Check if a request exceeds the rate limit"""
        now = time.time()
        
        # Get rate limit for this endpoint or use default
        limit = self.endpoint_limits.get(endpoint, self.endpoint_limits['default'])
        rate, per = limit['rate'], limit['per']
        
        # Get recent requests within the time window
        key = f"{ip}:{endpoint}"
        recent = [t for t in self.ip_requests[key] if now - t < per]
        
        # Update the requests list
        self.ip_requests[key] = recent
        
        # Check if we've hit the limit
        if len(recent) >= rate:
            return True
        
        # Record this request
        self.ip_requests[key].append(now)
        return False

    @web.middleware
    async def middleware(self, request, handler):
        """
        aiohttp middleware that applies rate limiting
        """
        # Get client IP address
        ip = request.remote
        endpoint = request.path
        
        # Allow health check endpoints to bypass rate limiting
        if endpoint in ['/health', '/readiness', '/metrics']:
            return await handler(request)
        
        # Check if rate limited
        if self._is_rate_limited(ip, endpoint):
            logger.warning(f"Rate limit exceeded for IP {ip} on {endpoint}")
            return web.json_response({
                'success': False,
                'error': 'Too many requests. Please try again later.'
            }, status=429)
        
        return await handler(request)

# Import and apply the middleware in rest_routes.py
def setup_rest_app(auth_manager):
    app = web.Application(middlewares=[
        RateLimiter().middleware
    ])
    
    # ... rest of the existing setup code