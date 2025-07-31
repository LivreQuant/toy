# source/service/health.py
import logging
import asyncio
from aiohttp import web
from datetime import datetime

logger = logging.getLogger('health_service')

class HealthService:
    def __init__(self, market_data_service=None, http_port=50061):
        self.market_data_service = market_data_service
        self.http_port = http_port
        self.app = None
        self.runner = None
        self.site = None
        self.start_time = datetime.utcnow()

    async def setup(self):
        """Set up the health check HTTP server"""
        self.app = web.Application()
        
        # Set up routes
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/stats', self.stats_check)
        self.app.router.add_get('/metrics', self.metrics_check)
        
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
        """Health check handler with PostgreSQL focus"""
        uptime = datetime.utcnow() - self.start_time
        
        health_data = {
            'status': 'UP',
            'service': 'market-data-service',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'uptime_seconds': int(uptime.total_seconds()),
            'version': '2.0.0-postgresql',
            'storage': 'PostgreSQL only'
        }
        
        # Add service-specific health info if available
        if self.market_data_service:
            health_data['service_running'] = self.market_data_service.running
            health_data['subscribers'] = self.market_data_service.subscribers_count
            health_data['database_saves'] = self.market_data_service.database_saves
            health_data['database_errors'] = self.market_data_service.database_errors
            
        return web.json_response(health_data)

    async def stats_check(self, request):
        """Service statistics endpoint"""
        if not self.market_data_service:
            return web.json_response({'error': 'Service not available'}, status=503)
            
        stats = self.market_data_service.get_stats()
        return web.json_response(stats)

    async def metrics_check(self, request):
        """Prometheus-style metrics endpoint"""
        if not self.market_data_service:
            return web.Response(text='# Service not available\n', content_type='text/plain')
            
        stats = self.market_data_service.get_stats()
        
        metrics = [
            f"# HELP market_data_batches_total Total number of data batches generated",
            f"# TYPE market_data_batches_total counter", 
            f"market_data_batches_total {stats['batch_count']}",
            f"",
            f"# HELP market_data_updates_sent_total Total number of updates sent to subscribers",
            f"# TYPE market_data_updates_sent_total counter",
            f"market_data_updates_sent_total {stats['updates_sent']}",
            f"",
            f"# HELP market_data_database_saves_total Total number of successful database saves",
            f"# TYPE market_data_database_saves_total counter",
            f"market_data_database_saves_total {stats['database_saves']}",
            f"",
            f"# HELP market_data_database_errors_total Total number of database errors",
            f"# TYPE market_data_database_errors_total counter", 
            f"market_data_database_errors_total {stats['database_errors']}",
            f"",
            f"# HELP market_data_subscribers_current Current number of active subscribers",
            f"# TYPE market_data_subscribers_current gauge",
            f"market_data_subscribers_current {stats['subscribers_count']}",
            f"",
            f"# HELP market_data_symbols_total Total number of symbols being tracked",
            f"# TYPE market_data_symbols_total gauge", 
            f"market_data_symbols_total {len(stats['symbols'])}",
            f"",
            f"# HELP market_data_fx_pairs_total Total number of FX pairs being tracked",
            f"# TYPE market_data_fx_pairs_total gauge",
            f"market_data_fx_pairs_total {len(stats['fx_pairs'])}",
            f""
        ]
        
        return web.Response(text='\n'.join(metrics), content_type='text/plain')