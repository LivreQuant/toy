# source/api/rest/health.py - Enhanced version

import logging
import asyncio
import time
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
        self.startup_time = time.time()
        self.initialization_complete = False
        self.services_ready = {
            'database': False,
            'market_data': False,
            'order_manager': False,
            'grpc_server': False
        }

    async def setup(self):
        """Set up the health check HTTP server"""
        self.app = web.Application()
        
        # Set up routes
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/readiness', self.readiness_check)
        self.app.router.add_get('/metrics', self.metrics_endpoint)
        self.app.router.add_get('/status', self.detailed_status)  # New detailed status endpoint
        
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

    def mark_service_ready(self, service_name: str, ready: bool = True):
        """Mark a service component as ready"""
        if service_name in self.services_ready:
            self.services_ready[service_name] = ready
            logger.info(f"Service component '{service_name}' marked as {'ready' if ready else 'not ready'}")
            
            # Check if all services are ready
            if all(self.services_ready.values()) and not self.initialization_complete:
                self.initialization_complete = True
                logger.info("All service components are ready - simulator fully operational")

    async def health_check(self, request):
        """
        Simple liveness probe handler
        Returns 200 OK if the basic service is running
        """
        return web.json_response({
            'status': 'UP',
            'service': 'exchange-simulator',
            'timestamp': time.time(),
            'uptime_seconds': time.time() - self.startup_time
        })

    async def readiness_check(self, request):
        """
        Enhanced readiness probe handler
        Maps to simulator status progression:
        - Starting: Basic service running but not all components ready
        - Spinning: Components initializing
        - Running: All components ready and operational
        """
        current_time = time.time()
        uptime = current_time - self.startup_time
        
        # Determine readiness status
        if not self.initialization_complete:
            # Still initializing - check individual components
            ready_count = sum(1 for ready in self.services_ready.values() if ready)
            total_count = len(self.services_ready)
            
            if ready_count == 0:
                status = "STARTING"
                status_code = 503  # Service Unavailable
            elif ready_count < total_count:
                status = "SPINNING"  
                status_code = 503  # Service Unavailable
            else:
                status = "RUNNING"
                status_code = 200  # Ready
                self.initialization_complete = True
        else:
            # Fully initialized - do health checks
            is_healthy = await self._check_component_health()
            if is_healthy:
                status = "RUNNING"
                status_code = 200
            else:
                status = "ERROR"
                status_code = 503

        return web.json_response({
            'status': status,
            'service': 'exchange-simulator',
            'timestamp': current_time,
            'uptime_seconds': uptime,
            'initialization_complete': self.initialization_complete,
            'services': self.services_ready.copy(),
            'ready_services': sum(1 for ready in self.services_ready.values() if ready),
            'total_services': len(self.services_ready)
        }, status=status_code)

    async def detailed_status(self, request):
        """
        Detailed status endpoint for debugging and monitoring
        """
        current_time = time.time()
        uptime = current_time - self.startup_time
        
        # Gather detailed status information
        status_info = {
            'service': 'exchange-simulator',
            'status': 'RUNNING' if self.initialization_complete else 'INITIALIZING',
            'timestamp': current_time,
            'uptime_seconds': uptime,
            'initialization_complete': self.initialization_complete,
            'startup_time': self.startup_time,
            'services': self.services_ready.copy()
        }

        # Add exchange manager status if available
        if self.exchange_manager:
            try:
                status_info['exchange_manager'] = {
                    'user_id': getattr(self.exchange_manager, 'user_id', 'unknown'),
                    'desk_id': getattr(self.exchange_manager, 'desk_id', 'unknown'),
                    'cash_balance': getattr(self.exchange_manager, 'cash_balance', 0),
                    'positions_count': len(getattr(self.exchange_manager, 'positions', {})),
                    'orders_count': len(getattr(self.exchange_manager, 'orders', {})),
                    'market_data_symbols': len(getattr(self.exchange_manager, 'current_market_data', {}))
                }
            except Exception as e:
                status_info['exchange_manager'] = {'error': str(e)}

        return web.json_response(status_info)

    async def _check_component_health(self) -> bool:
        """Check health of all components"""
        try:
            # Check database connection
            if self.exchange_manager and hasattr(self.exchange_manager, 'database_manager'):
                db_healthy = await self.exchange_manager.database_manager.check_connection()
                if not db_healthy:
                    return False

            # Check market data client
            if self.exchange_manager and hasattr(self.exchange_manager, 'market_data_client'):
                if not getattr(self.exchange_manager.market_data_client, 'running', False):
                    return False

            # Check order manager
            if self.exchange_manager and hasattr(self.exchange_manager, 'order_manager'):
                if not getattr(self.exchange_manager.order_manager, 'connected', False):
                    return False

            return True
        except Exception as e:
            logger.error(f"Error checking component health: {e}")
            return False

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