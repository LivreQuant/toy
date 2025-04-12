# source/api/server.py
"""
Session service main server with dependency injection.
"""
import logging
import asyncio
import time
import aiohttp_cors
from aiohttp import web

from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from source.config import config
from source.utils.di import DependencyContainer

from source.db.manager import StoreManager
from source.core.stream.manager import StreamManager
from source.core.session.manager import SessionManager
from source.core.simulator.manager import SimulatorManager

from source.clients.exchange import ExchangeClient
from source.clients.k8s import KubernetesClient

from source.api.rest.routes import setup_rest_routes
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
    """Main session service server using dependency injection"""

    def __init__(self):
        """Initialize server components"""
        # Apply middleware directly during Application creation for cleaner setup
        self.app = web.Application(middlewares=[
            metrics_middleware,
            error_handling_middleware,
            tracing_middleware
        ])
        self._runner = None
        self.running = False
        self.initialized = False
        self.shutdown_event = asyncio.Event()
        
        # Create dependency container
        self.di = DependencyContainer()
        
    async def initialize(self):
        """Initialize all server components using dependency injection"""
        if self.initialized:
            logger.debug("Server already initialized.")
            return

        logger.info("Initializing server components")
        
        # Initialize dependency container with factories
        self._register_dependencies()
        
        # Connect to database first
        store_manager = self.di.get('store_manager')
        try:
            await store_manager.connect()
            logger.info("Database connections established.")
        except Exception as e:
            logger.critical(f"Failed to connect to databases: {e}. Cannot start server.", exc_info=True)
            raise RuntimeError(f"Database connection failed: {e}") from e
            
        # Resolve core components - the container will handle dependency resolution
        session_manager = self.di.get('session_manager')
        websocket_manager = self.di.get('websocket_manager')
        
        # Start background tasks now that everything is initialized
        await session_manager.start_session_tasks()
        logger.info("Session cleanup tasks started.")

        # Make components available in application context
        self.app['exchange_client'] = self.di.get('exchange_client')
        self.app['k8s_client'] = self.di.get('k8s_client')
        self.app['stream_manager'] = self.di.get('stream_manager')
        self.app['store_manager'] = store_manager
        self.app['simulator_manager'] = self.di.get('simulator_manager')
        self.app['session_manager'] = session_manager
        self.app['websocket_manager'] = websocket_manager

        # Set up routes
        setup_rest_routes(self.app)
        logger.info("REST routes configured.")

        # Register WebSocket handler
        self.app.router.add_get('/ws', websocket_manager.handle_connection)
        logger.info("WebSocket route '/ws' configured.")

        # Add health check endpoints
        self.app.router.add_get('/health', health_check)
        self.app.router.add_get('/readiness', self.readiness_check)
        self.app.router.add_get('/metrics', metrics_endpoint)
        logger.info("Health, readiness, and metrics routes configured.")

        # Set up CORS
        self._setup_cors()
        logger.info("CORS configured.")

        self.initialized = True
        logger.info("Server initialization complete")
    
    def _register_dependencies(self):
        """Register all component factories and their dependencies"""
        # Register simple components with no dependencies
        self.di.register_instance('store_manager', StoreManager())
        self.di.register('exchange_client', lambda: ExchangeClient(), [])
        self.di.register('k8s_client', lambda: KubernetesClient(), [])
        self.di.register('stream_manager', lambda: StreamManager(), [])
        
        # Register simulator manager which depends on store_manager and k8s_client
        self.di.register(
            'simulator_manager',
            lambda store_manager, k8s_client: SimulatorManager(store_manager, k8s_client),
            ['store_manager', 'k8s_client']
        )
        
        # Register session manager with its dependencies
        self.di.register(
            'session_manager',
            lambda store_manager, exchange_client, stream_manager, simulator_manager:
                SessionManager(
                    store_manager, 
                    exchange_client=exchange_client,
                    stream_manager=stream_manager,
                    simulator_manager=simulator_manager
                ),
            ['store_manager', 'exchange_client', 'stream_manager', 'simulator_manager']
        )
        
        # Register websocket manager which depends on session_manager
        self.di.register(
            'websocket_manager',
            lambda stream_manager, session_manager: WebSocketManager(session_manager, stream_manager),
            ['session_manager']
        )

    # The rest of the methods remain largely unchanged
    async def start(self):
        """Start the server after initialization"""
        if not self.initialized:
            logger.warning("Server not initialized. Calling initialize().")
            await self.initialize()

        if self.running:
            logger.warning("Server start() called but already running.")
            return

        host = config.server.host
        port = config.server.port

        # Start the application runner
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()

        site = web.TCPSite(self._runner, host, port, shutdown_timeout=config.server.shutdown_timeout)
        try:
            await site.start()
            self.running = True
            logger.info(f"Server successfully started at http://{host}:{port}")
        except OSError as e:
            logger.critical(f"Failed to start server on {host}:{port}: {e}. Port likely in use.", exc_info=True)
            await self._runner.cleanup()
            raise RuntimeError(f"Failed to bind to {host}:{port}") from e

    async def shutdown(self):
        """Gracefully shut down the server and clean up resources"""
        if self.shutdown_event.is_set():
            logger.info("Shutdown already complete or in progress.")
            return
        if not self.running:
            logger.warning("Shutdown called but server wasn't running.")
            self.shutdown_event.set()
            return

        logger.info("Initiating graceful shutdown...")
        self.running = False  # Mark as not running early

        # Get components from dependency container
        session_manager = self.di.get('session_manager')
        websocket_manager = self.di.get('websocket_manager')
        exchange_client = self.di.get('exchange_client')
        store_manager = self.di.get('store_manager')

        # Clean up sessions
        logger.info("Stopping session manager cleanup task...")
        await session_manager.cleanup_pod_sessions(config.kubernetes.pod_name)
        await session_manager.stop_cleanup_task()

        # Close WebSocket connections
        logger.info("Closing all WebSocket connections...")
        await websocket_manager.close_all_connections("Server is shutting down")

        # Close external connections
        await exchange_client.close()
        await store_manager.close()

        # Stop the AppRunner
        if self._runner:
            logger.info("Cleaning up aiohttp AppRunner...")
            await self._runner.cleanup()

        logger.info("Server shutdown sequence finished.")
        self.shutdown_event.set()

    async def readiness_check(self, request):
        """Comprehensive readiness check for dependencies"""
        checks = {}
        all_ready = True

        # Get dependencies from container
        store_manager = self.di.get('store_manager')

        # Check database connections
        db_ready = await store_manager.check_connection()
        checks['database'] = 'UP' if db_ready else 'DOWN'
        if not db_ready:
            all_ready = False
            logger.warning("Database connection check failed!")

        status_code = 200 if all_ready else 503  # Service Unavailable if not ready
        return web.json_response({
            'status': 'READY' if all_ready else 'NOT READY',
            'timestamp': time.time(),
            'pod': config.kubernetes.pod_name,
            'checks': checks
        }, status=status_code)

    def _setup_cors(self):
        """Set up CORS for API endpoints"""
        # Allow all origins specified in config, or '*' if none/empty
        origins = config.server.cors_allowed_origins or ["*"]
        logger.info(f"Setting up CORS for origins: {origins}")

        cors_options = aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",  # Be more specific in production if possible
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]  # Include common methods
        )
        defaults = {origin: cors_options for origin in origins}

        cors = aiohttp_cors.setup(self.app, defaults=defaults)

        for route in list(self.app.router.routes()):
            try:
                cors.add(route)
            except ValueError:
                pass

    async def wait_for_shutdown(self):
        """Wait until the shutdown process is complete."""
        logger.info("Server running. Waiting for shutdown signal...")
        await self.shutdown_event.wait()
        logger.info("Shutdown signal received and processed. Exiting wait.")