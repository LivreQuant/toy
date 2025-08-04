# source/api/rest/health.py - Updated for orchestration architecture
import logging
import asyncio
import time
import grpc
from aiohttp import web
from typing import Optional, Dict, Any

logger = logging.getLogger('health_service')

class OrchestrationHealthService:
    def __init__(self, 
                 exchange_group_manager=None, 
                 service_manager=None,
                 http_port=50056):
        """
        Initialize health check service for orchestration architecture
        
        Args:
            exchange_group_manager: Reference to exchange group manager
            service_manager: Reference to CoreExchangeServiceManager
            http_port: HTTP port for health server (separate from gRPC port)
        """
        self.exchange_group_manager = exchange_group_manager
        self.service_manager = service_manager
        self.http_port = http_port
        self.app = None
        self.runner = None
        self.site = None
        self.startup_time = time.time()
        self.initialization_complete = False
        
        # Track orchestration services - ADD exchange_registration
        self.services_ready = {
            'core_exchange': False,
            'market_data_client': False,
            'session_service': False,
            'conviction_service': False,
            'exchange_registration': False  # ADD THIS LINE
        }

    async def setup(self):
        """Set up the health check HTTP server"""
        self.app = web.Application()
        
        # Set up routes
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/readiness', self.readiness_check)
        self.app.router.add_get('/metrics', self.metrics_endpoint)
        self.app.router.add_get('/status', self.detailed_status)
        
        # Create and start the app
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        # Bind to health check port
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
                logger.info("All service components are ready - exchange fully operational")
        else:
            logger.warning(f"Unknown service component: {service_name}")

    async def health_check(self, request):
        """
        Simple liveness probe handler - returns 200 if service is running
        """
        return web.json_response({
            'status': 'UP',
            'service': 'exchange-orchestration',
            'timestamp': time.time(),
            'uptime_seconds': time.time() - self.startup_time
        })

    async def readiness_check(self, request):
        """
        Enhanced readiness probe for orchestration services
        """
        current_time = time.time()
        uptime = current_time - self.startup_time
        
        # Check core components
        core_ready = self._check_core_exchange_ready()
        market_data_ready = self._check_market_data_ready()
        services_ready = self._check_optional_services_ready()
        
        # Determine overall readiness
        is_ready = core_ready and (market_data_ready or uptime > 60)  # Allow startup time
        status_code = 200 if is_ready else 503
        
        status = "RUNNING" if is_ready else "STARTING"
        
        return web.json_response({
            'status': status,
            'service': 'exchange-orchestration',
            'timestamp': current_time,
            'uptime_seconds': uptime,
            'core_exchange_ready': core_ready,
            'market_data_connected': market_data_ready,
            'services': self.services_ready.copy(),
            'enabled_services': list(self.service_manager.enabled_services) if self.service_manager else [],
            'user_count': len(self.exchange_group_manager.get_all_users()) if self.exchange_group_manager else 0
        }, status=status_code)

    async def metrics_endpoint(self, request):
        """Metrics endpoint for monitoring"""
        metrics = {
            'uptime_seconds': time.time() - self.startup_time,
            'users_count': len(self.exchange_group_manager.get_all_users()) if self.exchange_group_manager else 0,
            'enabled_services_count': len(self.service_manager.enabled_services) if self.service_manager else 0,
            'core_exchange_ready': self._check_core_exchange_ready(),
            'market_data_connected': self._check_market_data_ready(),
            'services_ready': self.services_ready.copy()
        }
        
        return web.json_response(metrics)

    async def detailed_status(self, request):
        """Detailed status for debugging"""
        status = {
            'timestamp': time.time(),
            'uptime_seconds': time.time() - self.startup_time,
            'initialization_complete': self.initialization_complete,
            'core_exchange': {
                'ready': self._check_core_exchange_ready(),
                'users': self.exchange_group_manager.get_all_users() if self.exchange_group_manager else [],
                'last_snap_time': str(self.exchange_group_manager.last_snap_time) if self.exchange_group_manager else None
            },
            'market_data': {
                'connected': self._check_market_data_ready(),
                'host': getattr(self.service_manager, 'market_data_host', 'unknown') if self.service_manager else 'unknown',
                'port': getattr(self.service_manager, 'market_data_port', 'unknown') if self.service_manager else 'unknown'
            },
            'services': self.services_ready.copy(),
            'enabled_services': list(self.service_manager.enabled_services) if self.service_manager else []
        }
        
        return web.json_response(status)

    def _check_core_exchange_ready(self) -> bool:
        """Check if core exchange is ready"""
        if not self.exchange_group_manager:
            return False
        
        try:
            users = self.exchange_group_manager.get_all_users()
            return len(users) > 0 and self.exchange_group_manager.last_snap_time is not None
        except Exception:
            return False

    def _check_market_data_ready(self) -> bool:
        """Check if market data connection is ready"""
        if not self.service_manager:
            return False
        
        return getattr(self.service_manager, 'market_data_connected', False)

    def _check_optional_services_ready(self) -> bool:
        """Check if optional services are ready"""
        if not self.service_manager:
            return True  # No optional services to check
        
        # Optional services don't block readiness, just report status
        return True