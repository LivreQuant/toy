"""
Session service main server with dependency injection for single-user mode.
Enhanced with background simulator management.
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
from source.core.simulator.background_manager import BackgroundSimulatorManager

from source.clients.exchange import ExchangeClient
from source.clients.k8s import KubernetesClient

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


class SessionServer:
    def __init__(self):
        # Create state manager
        self.state_manager = StateManager()

        # Apply middleware
        self.app = web.Application(middlewares=[
            metrics_middleware,
            error_handling_middleware,
            tracing_middleware
        ])
        self._runner = None
        self.running = False
        self.initialized = False
        self.shutdown_event = asyncio.Event()

        # Initialize other managers and clients to None initially
        self.store_manager = None
        self.exchange_client = None
        self.k8s_client = None
        self.stream_manager = None
        self.simulator_manager = None
        self.session_manager = None
        self.websocket_manager = None
        self.health_manager = None
        self.background_simulator_manager = None

    async def initialize(self):
        """Initialize all server components"""
        if self.initialized:
            logger.debug("Server already initialized.")
            return

        logger.info("Initializing server components")

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

        # Create clients
        self.exchange_client = ExchangeClient()
        self.k8s_client = KubernetesClient()
        logger.info(f"Kubernetes client initialized: {self.k8s_client is not None}")

        # Create managers
        self.stream_manager = StreamManager()
        self.simulator_manager = SimulatorManager(self.store_manager, self.exchange_client, self.k8s_client)

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

        # Create background simulator manager
        self.background_simulator_manager = BackgroundSimulatorManager(
            self.simulator_manager,
            self.websocket_manager
        )

        # Wire up the background simulator manager to session manager
        self.session_manager.set_background_simulator_manager(self.background_simulator_manager)

        # Create health check manager for this session only
        from source.core.health.manager import HealthCheckManager
        self.health_manager = HealthCheckManager(
            self.session_manager,
            check_interval=30,  # Check every 30 seconds
            timeout_threshold=120  # Mark unhealthy after 2 minutes
        )

        # Store components in app context
        self.app['store_manager'] = self.store_manager
        self.app['exchange_client'] = self.exchange_client
        self.app['k8s_client'] = self.k8s_client
        self.app['stream_manager'] = self.stream_manager
        self.app['state_manager'] = self.state_manager
        self.app['session_manager'] = self.session_manager
        self.app['simulator_manager'] = self.simulator_manager
        self.app['websocket_manager'] = self.websocket_manager
        self.app['health_manager'] = self.health_manager
        self.app['background_simulator_manager'] = self.background_simulator_manager

        # Set up routes
        self._setup_routes()

        # Set up CORS
        self._setup_cors()

        self.initialized = True
        logger.info(f"Server initialization complete!")

    async def start(self):
        """Start the server"""
        # Start background simulator manager
        await self.background_simulator_manager.start()
        logger.info("Background simulator manager started")
        
        # Start health check manager for this session
        await self.health_manager.start()
        logger.info("Session health check manager started")
        
        # Start web application
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
        
        # Stop background simulator manager
        if hasattr(self, 'background_simulator_manager') and self.background_simulator_manager:
            await self.background_simulator_manager.stop()
            logger.info("Background simulator manager stopped")
        
        # Stop health check manager
        if hasattr(self, 'health_manager') and self.health_manager:
            await self.health_manager.stop()
            logger.info("Session health check manager stopped")
        
        # Stop other components
        if hasattr(self, 'websocket_manager') and self.websocket_manager:
            await self.websocket_manager.close_all_connections("Server shutting down")
            
        if hasattr(self, 'session_manager') and self.session_manager:
            await self.session_manager.cleanup_session()
            
        if hasattr(self, 'exchange_client') and self.exchange_client:
            await self.exchange_client.close()
            
        if hasattr(self, 'k8s_client') and self.k8s_client:
            await self.k8s_client.close()
            
        if hasattr(self, 'store_manager') and self.store_manager:
            await self.store_manager.close()
        
        # Perform cleanup tasks
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
        
        # Add health check endpoints for this session's simulator only
        self.app.router.add_post('/api/health/check-current-simulator', self.check_current_simulator)
        self.app.router.add_get('/api/health/simulator-status', self.get_simulator_status)

        logger.info("All routes configured")

    def _setup_cors(self):
        """Set up CORS for API endpoints"""
        # Allow all origins specified in config, or '*' if none/empty
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
        """
        Comprehensive readiness check for session service.
        
        Checks:
        - Database connectivity
        - Session state
        - Health manager status
        - Background simulator manager status
        """
        checks = {
            'database': 'DOWN',
            'session_state': 'DOWN',
            'health_manager': 'DOWN',
            'background_simulator_manager': 'DOWN'
        }
        
        all_ready = True

        # Check database connections
        try:
            db_ready = await self.store_manager.check_connection()
            checks['database'] = 'UP' if db_ready else 'DOWN'
            if not db_ready:
                all_ready = False
                logger.warning("Database connection check failed!")
        except Exception as e:
            logger.error(f"Database connection check error: {e}")
            all_ready = False

        # Check session state
        try:
            session_ready = self.session_manager.state_manager.is_ready()
            checks['session_state'] = 'UP' if session_ready else 'DOWN'
            if not session_ready:
                all_ready = False
        except Exception as e:
            logger.error(f"Session state check error: {e}")
            all_ready = False

        # Check health manager
        try:
            health_manager_ready = self.health_manager and self.health_manager.running
            checks['health_manager'] = 'UP' if health_manager_ready else 'DOWN'
            if not health_manager_ready:
                all_ready = False
        except Exception as e:
            logger.error(f"Health manager check error: {e}")
            all_ready = False

        # Check background simulator manager
        try:
            bg_sim_ready = self.background_simulator_manager and self.background_simulator_manager.running
            checks['background_simulator_manager'] = 'UP' if bg_sim_ready else 'DOWN'
            if not bg_sim_ready:
                all_ready = False
        except Exception as e:
            logger.error(f"Background simulator manager check error: {e}")
            all_ready = False

        status_code = 200 if all_ready else 503
        return web.json_response({
            'status': 'READY' if all_ready else 'NOT READY',
            'timestamp': time.time(),
            'pod': config.kubernetes.pod_name,
            'checks': checks
        }, status=status_code)

    async def check_current_simulator(self, request):
        """Force health check on the current session's simulator"""
        try:
            health_manager = request.app['health_manager']
            if not health_manager:
                return web.json_response({
                    'error': 'Health manager not available'
                }, status=503)

            is_healthy, reason = await health_manager.force_check_current_simulator()
            
            return web.json_response({
                'healthy': is_healthy,
                'reason': reason,
                'timestamp': time.time(),
                'pod': config.kubernetes.pod_name
            })
        except Exception as e:
            logger.error(f"Error in current simulator health check: {e}")
            return web.json_response({
                'error': str(e),
                'healthy': False,
                'timestamp': time.time()
            }, status=500)

    async def get_simulator_status(self, request):
        """Get status of the current session's simulator"""
        try:
            health_manager = request.app['health_manager']
            background_sim_manager = request.app['background_simulator_manager']
            
            if not health_manager:
                return web.json_response({
                    'error': 'Health manager not available'
                }, status=503)

            status = health_manager.get_current_simulator_status()
            
            # Add background simulator manager status
            if background_sim_manager:
                session_id = status.get('active_session_id')
                if session_id:
                    bg_status = background_sim_manager.get_session_status(session_id)
                    status['background_status'] = bg_status
                    
            status['timestamp'] = time.time()
            status['pod'] = config.kubernetes.pod_name
            
            return web.json_response(status)
        except Exception as e:
            logger.error(f"Error getting simulator status: {e}")
            return web.json_response({
                'error': str(e),
                'timestamp': time.time()
            }, status=500)