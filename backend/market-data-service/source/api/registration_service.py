# src/api/registration_service.py
import logging
import time
import asyncio
from aiohttp import web
from typing import Dict, Any

from src.distributor.market_data_distributor import MarketDataDistributor
from src.config import config

logger = logging.getLogger(__name__)


class RegistrationService:
    """
    HTTP API service for exchange simulators to register with the distributor.
    Also provides health check and status endpoints.
    """
    
    def __init__(self, distributor: MarketDataDistributor, host: str = None, port: int = None):
        """
        Initialize the registration service.
        
        Args:
            distributor: Market data distributor instance
            host: Host address to bind to (optional, uses config if not provided)
            port: Port to listen on (optional, uses config if not provided)
        """
        self.distributor = distributor
        self.host = host or config.API_HOST
        self.port = port or config.API_PORT
        self.app = None
        self.runner = None
        self.site = None
        self.started_at = time.time()
        
        logger.info(f"Registration service initialized on {self.host}:{self.port}")
    
    async def setup(self):
        """Set up the HTTP server for registration"""
        self.app = web.Application()
        
        # Set up routes
        self.app.router.add_post('/register', self.register_handler)
        self.app.router.add_post('/unregister', self.unregister_handler)
        self.app.router.add_get('/health', self.health_handler)
        self.app.router.add_get('/status', self.status_handler)
        
        # Add CORS middleware
        self.app.router.add_options('/{tail:.*}', self._preflight_handler)
        self.app.middlewares.append(self._cors_middleware)
        
        # Create and start the app
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        
        logger.info(f"Registration service started on http://{self.host}:{self.port}")
    
    async def shutdown(self):
        """Shutdown the HTTP server"""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        
        logger.info("Registration service stopped")
    
    @staticmethod
    async def _preflight_handler(request):
        """Handle CORS preflight requests"""
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, X-Requested-With'
        }
        return web.Response(status=200, headers=headers)
    
    @staticmethod
    async def _cors_middleware(app, handler):
        """CORS middleware for all responses"""
        async def middleware_handler(request):
            response = await handler(request)
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response
        return middleware_handler
    
    async def register_handler(self, request):
        """
        Handle registration requests from exchange simulators.
        
        Expected POST body:
        {
            "host": "hostname",
            "port": 50055 (optional)
        }
        """
        try:
            data = await request.json()
            host = data.get('host')
            port = data.get('port')
            
            if not host:
                return web.json_response(
                    {'error': 'Host is required'}, 
                    status=400
                )
            
            success = await self.distributor.register_client(host, port)
            
            if success:
                return web.json_response({
                    'success': True,
                    'message': f'Registered client at {host}'
                })
            else:
                return web.json_response({
                    'success': False,
                    'message': f'Failed to connect to client at {host}'
                }, status=500)
        
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return web.json_response({
                'error': str(e)
            }, status=500)
    
    async def unregister_handler(self, request):
        """
        Handle unregistration requests from exchange simulators.
        
        Expected POST body:
        {
            "host": "hostname",
            "port": 50055 (optional)
        }
        """
        try:
            data = await request.json()
            host = data.get('host')
            port = data.get('port')
            
            if not host:
                return web.json_response(
                    {'error': 'Host is required'}, 
                    status=400
                )
            
            success = await self.distributor.unregister_client(host, port)
            
            if success:
                return web.json_response({
                    'success': True,
                    'message': f'Unregistered client at {host}'
                })
            else:
                return web.json_response({
                    'success': False,
                    'message': f'Client not found at {host}'
                }, status=404)
        
        except Exception as e:
            logger.error(f"Unregistration error: {e}")
            return web.json_response({
                'error': str(e)
            }, status=500)
    
    async def health_handler(self, request):
        """
        Health check endpoint for Kubernetes liveness/readiness probes.
        Returns 200 OK if the service is running.
        """
        return web.json_response({
            'status': 'UP',
            'service': 'market-data-distributor',
            'timestamp': time.time(),
            'uptime': int(time.time() - self.started_at)
        })
    
    async def status_handler(self, request):
        """
        Status endpoint for monitoring the distributor.
        Returns detailed status information.
        """
        distributor_status = self.distributor.get_status()
        
        return web.json_response({
            'status': 'UP',
            'service': 'market-data-distributor',
            'timestamp': time.time(),
            'uptime': int(time.time() - self.started_at),
            'distributor': distributor_status
        })
        