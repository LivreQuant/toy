# source/api/server.py
"""
Session service main server.
Coordinates all components and handles HTTP/WebSocket/GRPC endpoints.
"""
import logging
import asyncio
import time
from typing import Optional
import aiohttp_cors
from aiohttp import web

from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from source.config import config

from source.db.manager import StoreManager
from source.core.session.manager import SessionManager
from source.core.simulator.manager import SimulatorManager

from source.api.clients.auth_client import AuthClient
from source.api.clients.exchange_client import ExchangeClient
from source.api.rest.routes import setup_rest_routes
from source.api.rest.middleware import metrics_middleware
from source.api.websocket.manager import WebSocketManager
from source.core.stream.manager import StreamManager

from source.utils.middleware import tracing_middleware
from source.utils.k8s_client import KubernetesClient

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
    """Main session service server"""

    def __init__(self):
        """Initialize server components"""
        # Apply middleware directly during Application creation for cleaner setup
        self.app = web.Application(middlewares=[
            metrics_middleware,
            tracing_middleware
        ])
        self._runner = None
        self.running = False
        self.initialized = False
        self.shutdown_event = asyncio.Event()

        # Initialize component placeholders
        self.auth_client: Optional[AuthClient] = None
        self.exchange_client: Optional[ExchangeClient] = None
        self.k8s_client: Optional[KubernetesClient] = None
        self.websocket_manager: Optional[WebSocketManager] = None
        self.stream_manager: Optional[StreamManager] = None

        # Initialize managers
        self.store_manager: Optional[StoreManager] = StoreManager()
        self.session_manager: Optional[SessionManager] = None
        self.simulator_manager: Optional[SimulatorManager] = None

    async def initialize(self):
        """Initialize all server components"""
        if self.initialized:
            logger.debug("Server already initialized.")
            return

        logger.info("Initializing server components")

        # Initialize connection manager
        try:
            await self.store_manager.connect()
            logger.info("Database connections established.")
        except Exception as e:
            logger.critical(f"Failed to connect to databases: {e}. Cannot start server.", exc_info=True)
            raise RuntimeError(f"Database connection failed: {e}") from e

        # Initialize Internal API clients
        self.auth_client = AuthClient()
        self.exchange_client = ExchangeClient()
        logger.info("Internal API clients initialized.")

        # Initialize Kubernetes client
        self.k8s_client = KubernetesClient()

        # Initialize stream manager (now independent)
        self.stream_manager = StreamManager()
        logger.info("Stream manager initialized.")

        # Initialize simulator manager with its dependencies
        self.simulator_manager = SimulatorManager(
            self.store_manager,
            k8s_client=self.k8s_client
        )

        # Initialize session manager with stream manager
        self.session_manager = SessionManager(
            self.store_manager, 
            auth_client=self.auth_client,
            exchange_client=self.exchange_client,
            stream_manager=self.stream_manager,
            simulator_manager=self.simulator_manager
        )
        logger.info("Session manager initialized.")

        # Initialize WebSocket manager with session and stream managers
        self.websocket_manager = WebSocketManager(
            self.session_manager,
            self.stream_manager
        )
        logger.info("WebSocket manager initialized.")

        # Start background tasks
        await self.session_manager.start_session_tasks()
        logger.info("Session cleanup tasks started.")

        # Make components available in application context
        self.app['store_manager'] = self.store_manager
        self.app['session_manager'] = self.session_manager
        self.app['websocket_manager'] = self.websocket_manager
        self.app['auth_client'] = self.auth_client
        self.app['exchange_client'] = self.exchange_client
        self.app['stream_manager'] = self.stream_manager

        # Set up routes
        setup_rest_routes(self.app)
        logger.info("REST routes configured.")

        # Register WebSocket handler
        self.app.router.add_get('/ws', self.websocket_manager.handle_connection)
        logger.info("WebSocket route '/ws' configured.")

        # Add health check endpoints
        self.app.router.add_get('/health', health_check)
        self.app.router.add_get('/readiness', self.readiness_check)
        self.app.router.add_get('/metrics', metrics_endpoint)  # Expose Prometheus metrics
        logger.info("Health, readiness, and metrics routes configured.")

        # Set up CORS
        self._setup_cors()
        logger.info("CORS configured.")

        self.initialized = True
        logger.info("Server initialization complete")

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

        # Rest of the shutdown logic remains largely the same
        if self.session_manager:
            logger.info("Stopping session manager cleanup task...")
            await self.session_manager.cleanup_pod_sessions(config.kubernetes.pod_name)
            await self.session_manager.stop_cleanup_task()

        # Close WebSocket connections
        if self.websocket_manager:
            logger.info("Closing all WebSocket connections...")
            await self.websocket_manager.close_all_connections("Server is shutting down")

        # Close external connections
        if self.auth_client:
            await self.auth_client.close()
        if self.exchange_client:
            await self.exchange_client.close()
        if self.store_manager:
            await self.store_manager.close()

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

        # Check database connections
        if self.store_manager:
            db_ready = await self.store_manager.check_connection()
            checks['database'] = 'UP' if db_ready else 'DOWN'
            if not db_ready:
                all_ready = False
                logger.warning("Database connection check failed!")
        else:
            checks['database'] = 'NOT INITIALIZED'
            all_ready = False

        # Check Auth service
        if self.auth_client:
            auth_ready = await self.auth_client.check_service()
            checks['auth_service'] = 'UP' if auth_ready else 'DOWN'
            if not auth_ready:
                all_ready = False
        else:
            checks['auth_service'] = 'NOT INITIALIZED'
            all_ready = False

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
            allow_credentials=True,  # Important for cookies/auth headers
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
