# source/api/server.py
"""
Session service main server with dependency injection for single-user mode.
"""
import logging
import asyncio
import time
import uuid
import aiohttp_cors
from aiohttp import web

from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from source.config import config
from source.utils.di import DependencyContainer
from source.utils.state_manager import StateManager

from source.db.manager import StoreManager
from source.core.stream.manager import StreamManager
from source.core.session.manager import SessionManager
from source.core.simulator.manager import SimulatorManager

from source.clients.exchange import ExchangeClient
from source.clients.k8s import KubernetesClient

from source.api.rest.routes import setup_rest_routes
from source.api.websocket.manager import WebSocketManager

from source.utils.middleware import tracing_middleware, metrics_middleware, error_handling_middleware
from source.models.session import Session, SessionStatus

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
    """Main session service server using dependency injection for single-user mode"""

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
        
        # For single-user mode, we'll create and store the session ID at startup
        self.session_id = str(uuid.uuid4())
        self.user_id = None  # Will be set during initialization
            
        # Initialize state manager
        self.state_manager = StateManager()
        
    async def initialize(self):
        """Initialize all server components using dependency injection"""
        if self.initialized:
            logger.debug("Server already initialized.")
            return

        logger.info("Initializing server components")
            
        # Initialize state manager first
        await self.state_manager.initialize()
        
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
        
        # In single-user mode, we create a default user and session at startup
        # This would typically come from environment variables or config
        self.user_id = "default-user-123"  # In production, get this from config
        device_id = "server-instance"      # Default device ID for server-created session

        # Create the singleton session
        success = await self._create_singleton_session(session_manager, self.user_id, device_id)
        if not success:
            logger.critical("Failed to create singleton session! Cannot start server.")
            raise RuntimeError("Failed to initialize singleton session")
            
        # Start background tasks now that everything is initialized
        await session_manager.start_session_tasks()
        logger.info("Session cleanup tasks started.")

        # Make components available in application context
        self.app['state_manager'] = self.state_manager
        self.app['exchange_client'] = self.di.get('exchange_client')
        self.app['k8s_client'] = self.di.get('k8s_client')
        self.app['stream_manager'] = self.di.get('stream_manager')
        self.app['store_manager'] = store_manager
        self.app['simulator_manager'] = self.di.get('simulator_manager')
        self.app['session_manager'] = session_manager
        self.app['websocket_manager'] = websocket_manager
        
        # Add single-user mode context
        self.app['singleton_session_id'] = self.session_id
        self.app['singleton_user_id'] = self.user_id

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
        logger.info(f"Server initialization complete with singleton session {self.session_id}")
    
    async def _create_singleton_session(self, session_manager, user_id, device_id):
        """Create the singleton session for this server instance"""
        try:
            # We'll use our pre-generated session ID rather than creating a new one
            session = Session(
                session_id=self.session_id,
                user_id=user_id,
                status=SessionStatus.ACTIVE
            )
            
            # Store session directly 
            success = await session_manager.store_manager.session_store.create_session_with_id(
                self.session_id, user_id, device_id, ip_address="127.0.0.1"
            )
            
            if success:
                logger.info(f"Successfully created singleton session {self.session_id} for user {user_id}")
                return True
            else:
                logger.error("Failed to create singleton session in database")
                return False
                
        except Exception as e:
            logger.error(f"Error creating singleton session: {e}", exc_info=True)
            return False
    
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
                    simulator_manager=simulator_manager,
                    singleton_mode=True,
                    singleton_session_id=self.session_id
                ),
            ['store_manager', 'exchange_client', 'stream_manager', 'simulator_manager']
        )
        
        # Register websocket manager which depends on session_manager
        self.di.register(
            'websocket_manager',
            lambda session_manager, stream_manager: WebSocketManager(
                session_manager, 
                stream_manager,
                singleton_mode=True,
                singleton_session_id=self.session_id
            ),
            ['session_manager', 'stream_manager']
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

        # In single-user mode, clean up the singleton session
        logger.info(f"Cleaning up singleton session {self.session_id}...")
        await session_manager.cleanup_session(self.session_id)
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
        
        # Reset state manager
        logger.info("Resetting state manager...")
        await self.state_manager.close()
        
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

        # Check if service is ready for new connections
        service_ready = self.state_manager.is_ready()
        checks['service_state'] = 'READY' if service_ready else 'ACTIVE'
        if not service_ready:
            # Note: We don't set all_ready to False here - service can be healthy but busy
            logger.info("Service is currently active with a user session")
                
        # Include active user info in the response if available
        active_user = self.state_manager.get_active_user_id()
        if active_user:
            checks['active_user'] = active_user
            checks['active_session'] = self.state_manager.get_active_session_id()
            connection_time = self.state_manager.get_active_connection_time()
            if connection_time:
                checks['connection_duration'] = f"{int(time.time() - connection_time)} seconds"

        status_code = 200 if all_ready else 503  # Service Unavailable if not ready
        ready_status = "READY" if service_ready else "BUSY"
        
        return web.json_response({
            'status': 'HEALTHY' if all_ready else 'DEGRADED',
            'readyStatus': ready_status,
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
