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
        self.app.router.add_get('/market-status', self.market_status_check)
        self.app.router.add_get('/kubernetes', self.kubernetes_check)
        
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
        """Health check handler for Kubernetes 24/7/365 operation"""
        uptime = datetime.utcnow() - self.start_time
        
        health_data = {
            'status': 'UP',
            'service': 'market-data-service-24x7x365',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'uptime_seconds': int(uptime.total_seconds()),
            'version': '4.0.0-kubernetes-24x7x365',
            'storage': 'PostgreSQL only',
            'time_source': 'Current UTC converted to market timezone',
            'operation_mode': '24/7/365 Kubernetes continuous',
            'data_policy': 'Live during market hours, last available otherwise'
        }
        
        # Add service-specific health info if available
        if self.market_data_service:
            health_data['service_running'] = self.market_data_service.running
            health_data['subscribers'] = self.market_data_service.subscribers_count
            health_data['database_saves'] = self.market_data_service.database_saves
            health_data['database_errors'] = self.market_data_service.database_errors
            
            # Add current market status
            if hasattr(self.market_data_service, 'generator'):
                is_trading, market_status = self.market_data_service.generator.get_market_status()
                utc_time = self.market_data_service.generator.get_current_time()
                market_time = self.market_data_service.generator.get_current_market_time()
                
                health_data['market_status'] = market_status
                health_data['is_trading_hours'] = is_trading
                health_data['utc_time'] = utc_time.isoformat() + 'Z'
                health_data['market_time'] = market_time.strftime('%Y-%m-%d %H:%M:%S %Z')
                health_data['timezone'] = self.market_data_service.generator.timezone_name
                health_data['weekday'] = market_time.strftime('%A')
                health_data['is_weekend'] = market_time.weekday() >= 5
                health_data['data_type'] = 'live' if is_trading else 'last_available'
            
        return web.json_response(health_data)

    async def kubernetes_check(self, request):
        """Kubernetes-specific readiness and liveness check"""
        if not self.market_data_service or not self.market_data_service.running:
            return web.json_response({
                'ready': False,
                'live': False,
                'reason': 'Service not running'
            }, status=503)
        
        # Check database connectivity
        db_healthy = True
        try:
            if hasattr(self.market_data_service, 'db_manager') and self.market_data_service.db_manager.pool:
                # Database is connected
                pass
            else:
                db_healthy = False
        except:
            db_healthy = False
        
        kubernetes_data = {
            'ready': self.market_data_service.running and db_healthy,
            'live': self.market_data_service.running,
            'database_connected': db_healthy,
            'operation_mode': '24/7/365',
            'provides_data': 'always',
            'kubernetes_friendly': True,
            'restart_safe': True,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        
        if hasattr(self.market_data_service, 'generator'):
            is_trading, market_status = self.market_data_service.generator.get_market_status()
            kubernetes_data['current_data_type'] = 'live' if is_trading else 'last_available'
            kubernetes_data['market_status'] = market_status
        
        status_code = 200 if kubernetes_data['ready'] else 503
        return web.json_response(kubernetes_data, status=status_code)

    async def market_status_check(self, request):
        """Dedicated market status endpoint for 24/7/365 operation"""
        if not self.market_data_service or not hasattr(self.market_data_service, 'generator'):
            return web.json_response({'error': 'Service not available'}, status=503)
            
        generator = self.market_data_service.generator
        is_trading, market_status = generator.get_market_status()
        utc_time = generator.get_current_time()
        market_time = generator.get_current_market_time()
        
        market_data = {
            'market_status': market_status,
            'is_trading_hours': is_trading,
            'utc_time': utc_time.isoformat() + 'Z',
            'market_time': market_time.strftime('%Y-%m-%d %H:%M:%S %Z'),
            'timezone': generator.timezone_name,
            'weekday': market_time.strftime('%A'),
            'is_weekend': market_time.weekday() >= 5,
            'data_type': 'live' if is_trading else 'last_available',
            'kubernetes_operation': '24/7/365 continuous',
            'always_provides_data': True,
            'market_hours_config': {
                'pre_market': f"{generator.pre_market_start_hour:02d}:{generator.pre_market_start_minute:02d}-{generator.market_open_hour:02d}:{generator.market_open_minute:02d}",
                'regular': f"{generator.market_open_hour:02d}:{generator.market_open_minute:02d}-{generator.market_close_hour:02d}:{generator.market_close_minute:02d}",
                'after_hours': f"{generator.market_close_hour:02d}:{generator.market_close_minute:02d}-{generator.after_hours_end_hour:02d}:{generator.after_hours_end_minute:02d}",
                'timezone': generator.timezone_name
            },
            'current_prices': generator.get_current_prices(),
            'price_source': 'live_market' if is_trading else 'last_market'
        }
        
        return web.json_response(market_data)

    async def stats_check(self, request):
        """Service statistics endpoint with 24/7/365 operation info"""
        if not self.market_data_service:
            return web.json_response({'error': 'Service not available'}, status=503)
            
        stats = self.market_data_service.get_stats()
        return web.json_response(stats)

    async def metrics_check(self, request):
        """Prometheus-style metrics endpoint with Kubernetes and weekend metrics"""
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
            f"# HELP market_data_market_hours_updates_total Updates sent during market hours",
            f"# TYPE market_data_market_hours_updates_total counter",
            f"market_data_market_hours_updates_total {stats['market_hours_updates']}",
            f"",
            f"# HELP market_data_closed_hours_updates_total Updates sent during closed hours",
            f"# TYPE market_data_closed_hours_updates_total counter",
            f"market_data_closed_hours_updates_total {stats['closed_hours_updates']}",
            f"",
            f"# HELP market_data_weekend_updates_total Updates sent during weekends",
            f"# TYPE market_data_weekend_updates_total counter",
            f"market_data_weekend_updates_total {stats['weekend_updates']}",
            f"",
            f"# HELP market_data_is_trading_hours Current market trading status (1=trading, 0=closed)",
            f"# TYPE market_data_is_trading_hours gauge",
            f"market_data_is_trading_hours {1 if stats['is_trading_hours'] else 0}",
            f"",
            f"# HELP market_data_is_weekend Current weekend status (1=weekend, 0=weekday)",
            f"# TYPE market_data_is_weekend gauge",
            f"market_data_is_weekend {1 if stats['is_weekend'] else 0}",
            f"",
            f"# HELP market_data_kubernetes_operation Kubernetes 24/7/365 operation indicator (always 1)",
            f"# TYPE market_data_kubernetes_operation gauge",
            f"market_data_kubernetes_operation 1",
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