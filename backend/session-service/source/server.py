# source/api/server.py
"""
Session service main server with dependency injection for single-user mode.
"""
import logging
import asyncio
import time
import uuid
from aiohttp import web

from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from source.config import config
from source.core.state.state_manager import StateManager

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
    """Simplified session service server for singleton mode"""

    def __init__(self):
        """Initialize server components"""
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

        # Create state manager
        self.state_manager = StateManager()

        # Generate a stable session ID for this instance
        self.session_id = str(uuid.uuid4())
        self.user_id = config.singleton.user_id  # Get from config

    async def initialize(self):
        """Initialize all server components"""
        if self.initialized:
            logger.debug("Server already initialized.")
            return

        logger.info("Initializing server components")

        # Initialize state manager
        await self.state_manager.initialize()

        # Create core components directly without complex dependency injection
        store_manager = StoreManager()
        await store_manager.connect()

        # Create clients
        exchange_client = ExchangeClient()
        k8s_client = KubernetesClient()

        # Create managers
        stream_manager = StreamManager()
        simulator_manager = SimulatorManager(store_manager, k8s_client)

        # Create session manager with singleton session ID
        session_manager = SessionManager(
            store_manager,
            exchange_client,
            stream_manager,
            simulator_manager,
            self.session_id
        )

        # Create websocket manager
        websocket_manager = WebSocketManager(session_manager, stream_manager)

        # Create singleton session
        success = await self._create_singleton_session(session_manager)
        if not success:
            raise RuntimeError("Failed to initialize singleton session")

        # Start background tasks
        await session_manager.start_session_tasks()

        # Store components in app context
        self.app['state_manager'] = self.state_manager
        self.app['store_manager'] = store_manager
        self.app['exchange_client'] = exchange_client
        self.app['k8s_client'] = k8s_client
        self.app['stream_manager'] = stream_manager
        self.app['simulator_manager'] = simulator_manager
        self.app['session_manager'] = session_manager
        self.app['websocket_manager'] = websocket_manager

        # Set up routes
        self._setup_routes()

        # Set up CORS
        self._setup_cors()

        self.initialized = True
        logger.info(f"Server initialization complete with singleton session {self.session_id}")

    def _setup_routes(self):
        """Set up all server routes"""
        # REST routes
        setup_rest_routes(self.app)

        # WebSocket route
        self.app.router.add_get('/ws', self.app['websocket_manager'].handle_connection)

        # Health check endpoints
        self.app.router.add_get('/health', health_check)
        self.app.router.add_get('/readiness', self.readiness_check)
        self.app.router.add_get('/metrics', metrics_endpoint)

        logger.info("All routes configured")

    async def _create_singleton_session(self, session_manager):
        """Create the singleton session for this server instance"""
        try:
            device_id = config.singleton.device_id

            # Store session directly
            success = await session_manager.store_manager.session_store.create_session_with_id(
                self.session_id, self.user_id, device_id, ip_address="127.0.0.1"
            )

            if success:
                logger.info(f"Successfully created singleton session {self.session_id} for user {self.user_id}")
                return True
            else:
                logger.error("Failed to create singleton session in database")
                return False

        except Exception as e:
            logger.error(f"Error creating singleton session: {e}", exc_info=True)
            return False
        