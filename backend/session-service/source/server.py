"""
Simplified session service server - connects to existing simulators.
"""
import logging
import asyncio
import time
import aiohttp_cors
from aiohttp import web

from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from source.config import config
from source.db.manager import StoreManager
from source.core.state.manager import StateManager
from source.core.stream.manager import StreamManager
from source.core.session.manager import SessionManager
from source.core.simulator.manager import SimulatorManager
from source.clients.exchange import ExchangeClient
from source.api.websocket.manager import WebSocketManager
from source.utils.middleware import tracing_middleware, metrics_middleware, error_handling_middleware

logger = logging.getLogger('server')


async def metrics_endpoint(request):
    """Prometheus metrics endpoint"""
    try:
        metrics_data = generate_latest()
        return web.Response(
            body=metrics_data,
            content_type=CONTENT_TYPE_LATEST
        )
    except Exception as e:
        logger.error(f"Error generating Prometheus metrics: {e}", exc_info=True)
        return web.Response(status=500, text="Error generating metrics")


async def health_check(request):
    """Simple liveness check endpoint"""
    return web.json_response({
        'status': 'UP',
        'timestamp': time.time(),
        'pod': config.kubernetes.pod_name
    })


async def processing_status_endpoint(request):
    """Get current processing configuration and statistics"""
    try:
        websocket_manager = request.app.get('websocket_manager')
        
        response_data = {
            'delta_enabled': config.websocket.enable_delta,
            'compression_enabled': config.websocket.enable_compression,
            'compression_threshold': config.websocket.compression_threshold,
            'compression_level': config.websocket.compression_level,
            'active_connections': websocket_manager.get_connection_count() if websocket_manager else 0,
            'processing_mode': websocket_manager._get_processing_description() if websocket_manager else 'UNKNOWN',
            'timestamp': time.time()
        }
        
        # Add processing statistics if available
        if websocket_manager:
            stats = websocket_manager.get_processing_statistics()
            response_data['statistics'] = stats
        
        return web.json_response(response_data)
        
    except Exception as e:
        logger.error(f"Error getting processing status: {e}", exc_info=True)
        return web.json_response({
            'error': 'Failed to get processing status',
            'timestamp': time.time()
        }, status=500)


async def toggle_processing_endpoint(request):
    """Toggle delta and/or compression on/off at runtime (POST endpoint)"""
    try:
        data = await request.json()
        enable_delta = data.get('enable_delta')
        enable_compression = data.get('enable_compression')
        
        if enable_delta is None and enable_compression is None:
            return web.json_response({
                'error': 'Must specify enable_delta and/or enable_compression parameter',
                'timestamp': time.time()
            }, status=400)
        
        websocket_manager = request.app.get('websocket_manager')
        if not websocket_manager:
            return web.json_response({
                'error': 'WebSocket manager not available',
                'timestamp': time.time()
            }, status=500)
        
        # Update the configuration
        old_delta = config.websocket.enable_delta
        old_compression = config.websocket.enable_compression
        
        if enable_delta is not None:
            config.websocket.enable_delta = bool(enable_delta)
        if enable_compression is not None:
            config.websocket.enable_compression = bool(enable_compression)
        
        # Reinitialize the WebSocket manager's processing system
        from source.core.stream.delta_manager import DeltaManager
        
        if config.websocket.enable_delta or config.websocket.enable_compression:
            # Enable processing
            websocket_manager.delta_manager = DeltaManager(
                enable_delta=config.websocket.enable_delta,
                enable_compression=config.websocket.enable_compression,
                compression_threshold=config.websocket.compression_threshold,
                compression_level=config.websocket.compression_level
            )
            websocket_manager.delta_enabled = config.websocket.enable_delta
            websocket_manager.compression_enabled = config.websocket.enable_compression
            logger.info(f"Processing updated at runtime - Delta: {'ON' if config.websocket.enable_delta else 'OFF'}, Compression: {'ON' if config.websocket.enable_compression else 'OFF'}")
        else:
            # Disable all processing
            websocket_manager.delta_manager = None
            websocket_manager.delta_enabled = False
            websocket_manager.compression_enabled = False
            logger.info("All processing DISABLED at runtime - sending raw data")
        
        return web.json_response({
            'success': True,
            'old_delta': old_delta,
            'old_compression': old_compression,
            'new_delta': config.websocket.enable_delta,
            'new_compression': config.websocket.enable_compression,
            'processing_mode': websocket_manager._get_processing_description(),
            'active_connections': websocket_manager.get_connection_count(),
            'timestamp': time.time()
        })
        
    except Exception as e:
        logger.error(f"Error toggling processing: {e}", exc_info=True)
        return web.json_response({
            'error': 'Failed to toggle processing',
            'details': str(e),
            'timestamp': time.time()
        }, status=500)


class SessionServer:
    def __init__(self):
        self.state_manager = StateManager()
        self.app = web.Application(middlewares=[
            metrics_middleware,
            error_handling_middleware,
            tracing_middleware
        ])
        self._runner = None
        self.running = False
        self.initialized = False
        self.shutdown_event = asyncio.Event()

        # Initialize components to None
        self.store_manager = None
        self.exchange_client = None
        self.stream_manager = None
        self.simulator_manager = None
        self.session_manager = None
        self.websocket_manager = None

    async def initialize(self):
        """Initialize all server components"""
        if self.initialized:
            logger.debug("Server already initialized.")
            return

        logger.info("Initializing server components")
        logger.info(f"WebSocket Delta: {'ENABLED' if config.websocket.enable_delta else 'DISABLED'}")
        logger.info(f"WebSocket Compression: {'ENABLED' if config.websocket.enable_compression else 'DISABLED'}")

        try:
            # Initialize state manager
            await self.state_manager.initialize()
        except Exception as e:
            logger.error(f"Failed to initialize state manager: {e}", exc_info=True)
            raise

        try:
            # Create store manager
            self.store_manager = StoreManager()
            await self.store_manager.connect()
        except Exception as e:
            logger.error(f"Failed to initialize store manager: {e}", exc_info=True)
            raise

        # Create clients and managers
        self.exchange_client = ExchangeClient()
        self.stream_manager = StreamManager()
        
        # Simplified simulator manager (connection-only with Kubernetes discovery)
        self.simulator_manager = SimulatorManager(self.store_manager, self.exchange_client)

        # Create session manager
        self.session_manager = SessionManager(
            self.store_manager,
            self.exchange_client,
            self.stream_manager,
            self.state_manager,
            self.simulator_manager,
        )

        # Create websocket manager
        self.websocket_manager = WebSocketManager(self.session_manager)

        # Store components in app context
        self.app['store_manager'] = self.store_manager
        self.app['exchange_client'] = self.exchange_client
        self.app['stream_manager'] = self.stream_manager
        self.app['state_manager'] = self.state_manager
        self.app['session_manager'] = self.session_manager
        self.app['simulator_manager'] = self.simulator_manager
        self.app['websocket_manager'] = self.websocket_manager

        # Set up routes
        self._setup_routes()
        self._setup_cors()

        self.initialized = True
        logger.info(f"Server initialization complete!")

    async def start(self):
        """Start the server"""
        app_runner = web.AppRunner(self.app)
        await app_runner.setup()
        site = web.TCPSite(
            app_runner,
            config.server.host,
            config.server.port
        )
        await site.start()
        logger.info(f"Server started on {config.server.host}:{config.server.port}")

    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Initiating server shutdown")
        
        # Stop components
        if hasattr(self, 'websocket_manager') and self.websocket_manager:
            await self.websocket_manager.close_all_connections("Server shutting down")
            
        if hasattr(self, 'session_manager') and self.session_manager:
            await self.session_manager.cleanup_session()
            
        if hasattr(self, 'exchange_client') and self.exchange_client:
            await self.exchange_client.close()
            
        if hasattr(self, 'store_manager') and self.store_manager:
            await self.store_manager.close()
        
        self.shutdown_event.set()

    async def wait_for_shutdown(self):
        """Wait for shutdown signal"""
        await self.shutdown_event.wait()

    def _setup_routes(self):
        """Set up all server routes"""
        # WebSocket route
        self.app.router.add_get('/ws', self.app['websocket_manager'].handle_connection)

        # Health check endpoints
        self.app.router.add_get('/health', health_check)
        self.app.router.add_get('/readiness', self.readiness_check)
        self.app.router.add_get('/metrics', metrics_endpoint)
        
        # Processing management endpoints
        self.app.router.add_get('/api/processing/status', processing_status_endpoint)
        self.app.router.add_post('/api/processing/toggle', toggle_processing_endpoint)

        logger.info("All routes configured")

    def _setup_cors(self):
        """Set up CORS for API endpoints"""
        origins = config.server.cors_allowed_origins or ["*"]
        logger.info(f"Setting up CORS for origins: {origins}")

        cors_options = aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
        )
        defaults = {origin: cors_options for origin in origins}

        cors = aiohttp_cors.setup(self.app, defaults=defaults)

        for route in list(self.app.router.routes()):
            try:
                cors.add(route)
            except ValueError:
                pass

    async def readiness_check(self, request):
        """Simplified readiness check"""
        checks = {
            'database': 'DOWN',
            'session_state': 'DOWN'
        }
        
        all_ready = True

        # Check database connections
        try:
            db_ready = await self.store_manager.check_connection()
            checks['database'] = 'UP' if db_ready else 'DOWN'
            if not db_ready:
                all_ready = False
        except Exception as e:
            logger.error(f"Database connection check error: {e}")
            all_ready = False

        # Check session state
        try:
            session_ready = self.state_manager.is_ready()
            checks['session_state'] = 'UP' if session_ready else 'DOWN'
            if not session_ready:
                all_ready = False
        except Exception as e:
            logger.error(f"Session state check error: {e}")
            all_ready = False

        status_code = 200 if all_ready else 503
        return web.json_response({
            'status': 'READY' if all_ready else 'NOT READY',
            'timestamp': time.time(),
            'pod': config.kubernetes.pod_name,
            'checks': checks,
            'delta_enabled': config.websocket.enable_delta,
            'compression_enabled': config.websocket.enable_compression
        }, status=status_code)