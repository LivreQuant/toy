# Add to source/api/rest/health.py in the market-data-service
import logging
import asyncio
from aiohttp import web

logger = logging.getLogger('health_service')

class HealthService:
    def __init__(self, http_port=50061):
        self.http_port = http_port
        self.app = None
        self.runner = None
        self.site = None

    async def setup(self):
        """Set up the health check HTTP server"""
        self.app = web.Application()
        
        # Set up routes
        self.app.router.add_get('/health', self.health_check)
        
        # Create and start the app
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        # Bind to the configured port
        self.site = web.TCPSite(self.runner, '0.0.0.0', self.http_port)
        await self.site.start()
        
        logger.info(f"Health check server started on http://0.0.0.0:{self.http_port}")
        return self.app

    async def shutdown(self):
        """Shutdown the health check server"""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        logger.info("Health check server stopped")

    async def health_check(self, request):
        """Simple health check handler"""
        return web.json_response({
            'status': 'UP',
            'service': 'market-data-service',
            'timestamp': asyncio.get_event_loop().time()
        })