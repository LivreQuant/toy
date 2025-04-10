# source/api/rest/health.py
"""
HTTP health check server for the exchange simulator.
Provides endpoints for kubernetes probes and monitoring.
"""
import logging
import asyncio
from aiohttp import web

logger = logging.getLogger('health_service')

class HealthService:
    def __init__(self, exchange_manager=None, http_port=50056):
        """
        Initialize health check service
        
        Args:
            exchange_manager: Reference to exchange manager for status checks
            http_port: HTTP port for health server (separate from gRPC port)
        """
        self.exchange_manager = exchange_manager
        self.http_port = http_port
        self.app = None
        self.runner = None
        self.site = None

    async def setup(self):
        """Set up the health check HTTP server"""
        self.app = web.Application()
        
        # Set up routes
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/readiness', self.readiness_check)
        self.app.router.add_get('/metrics', self.metrics_endpoint)
        
        # Create and start the app
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        # Bind to a different port than the gRPC server
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
        """
        Simple liveness probe handler
        Returns 200 OK if the service is running
        """
        return web.json_response({
            'status': 'UP',
            'service': 'exchange-simulator',
            'timestamp': asyncio.get_event_loop().time()
        })

    async def readiness_check(self, request):
        """
        Readiness probe handler
        Checks if the exchange simulator is fully initialized and ready
        """
        # This is a more comprehensive check than the liveness probe
        is_ready = True
        status_code = 200
        status_details = {}
        
        # Check exchange manager status if available
        if self.exchange_manager:
            try:
                # You could add more detailed checks here
                status_details['exchange_manager'] = 'READY'
            except Exception as e:
                is_ready = False
                status_code = 503  # Service Unavailable
                status_details['exchange_manager'] = f'ERROR: {str(e)}'
        
        return web.json_response({
            'status': 'READY' if is_ready else 'NOT READY',
            'service': 'exchange-simulator',
            'timestamp': asyncio.get_event_loop().time(),
            'details': status_details
        }, status=status_code)

    async def metrics_endpoint(self, request):
        """
        Metrics endpoint for monitoring
        Returns Prometheus metrics if metrics are enabled
        """
        try:
            from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
            
            metrics_data = generate_latest()
            return web.Response(
                body=metrics_data,
                content_type=CONTENT_TYPE_LATEST
            )
        except Exception as e:
            logger.error(f"Error generating metrics: {e}")
            return web.Response(
                status=500,
                text=f"Error generating metrics: {str(e)}"
            )