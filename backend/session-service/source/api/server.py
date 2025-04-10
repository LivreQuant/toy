# source/api/server.py
"""
Session service main server.
Coordinates all components and handles HTTP/WebSocket/GRPC endpoints.
"""
import logging
import asyncio
import json
import time
import signal
from typing import Any, Optional, List
import aiohttp_cors
from aiohttp import web

from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from source.config import config

from source.db.session_store import DatabaseManager

from source.utils.middleware import tracing_middleware

from source.api.clients.auth_client import AuthClient
from source.api.clients.exchange_client import ExchangeClient
from source.api.rest.routes import setup_rest_routes
from source.api.rest.middleware import metrics_middleware
from source.api.websocket.manager import WebSocketManager

from source.models.simulator import SimulatorStatus

from source.core.session.session_manager import SessionManager

logger = logging.getLogger('server')


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
        self.db_manager: Optional[DatabaseManager] = None
        self.auth_client: Optional[AuthClient] = None
        self.exchange_client: Optional[ExchangeClient] = None
        self.session_manager: Optional[SessionManager] = None
        self.websocket_manager: Optional[WebSocketManager] = None
        self.pubsub_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Initialize all server components"""
        if self.initialized:
            logger.debug("Server already initialized.")
            return

        logger.info("Initializing server components")

        # Initialize database
        try:
            self.db_manager = DatabaseManager()
            await self.db_manager.connect()
            logger.info("Database connection established.")
        except Exception as e:
            logger.critical(f"Failed to connect to database: {e}. Cannot start server.", exc_info=True)
            raise RuntimeError(f"Database connection failed: {e}") from e

        # Initialize Internal API clients
        self.auth_client = AuthClient()
        self.exchange_client = ExchangeClient()
        logger.info("Internal API clients initialized.")

        # Initialize session manager
        self.session_manager = SessionManager(
            self.db_manager,
            self.auth_client,
            self.exchange_client
        )
        logger.info("Session manager initialized.")

        # Start background tasks (ensure session_manager is initialized first)
        await self.session_manager.start_session_tasks()
        logger.info("Session cleanup task started.")

        # Initialize WebSocket manager (ensure session_manager is initialized first)
        self.websocket_manager = WebSocketManager(self.session_manager, self.db_manager)
        logger.info("WebSocket manager initialized.")

        # Make components available in application context
        self.app['db_manager'] = self.db_manager
        self.app['auth_client'] = self.auth_client
        self.app['exchange_client'] = self.exchange_client
        self.app['session_manager'] = self.session_manager
        self.app['websocket_manager'] = self.websocket_manager

        # Set up routes
        setup_rest_routes(self.app)
        logger.info("REST routes configured.")

        # Register WebSocket handler
        self.app.router.add_get('/ws', self.websocket_manager.handle_connection)
        logger.info("WebSocket route '/ws' configured.")

        # Add health check endpoints
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/readiness', self.readiness_check)
        self.app.router.add_get('/metrics', self.metrics_endpoint)  # Expose Prometheus metrics
        logger.info("Health, readiness, and metrics routes configured.")

        # Set up CORS
        self._setup_cors()
        logger.info("CORS configured.")

        # Set up signal handlers (can be here or in main.py)
        # Keeping them here as server class manages lifecycle
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self._handle_signal(s)))

        self.initialized = True
        logger.info("Server initialization complete")

    async def start(self):
        """Start the server after initialization"""
        if not self.initialized:
            logger.warning("Server not initialized. Calling initialize().")
            await self.initialize()  # Ensure initialized

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
            # Perform cleanup before exiting or raising
            await self._runner.cleanup()
            raise RuntimeError(f"Failed to bind to {host}:{port}") from e

    async def shutdown(self):
        """Gracefully shut down the server and clean up resources"""
        if self.shutdown_event.is_set():
            logger.info("Shutdown already complete or in progress.")
            return
        if not self.running:
            logger.warning("Shutdown called but server wasn't running.")
            # Still set the event to allow wait_for_shutdown to complete if called
            self.shutdown_event.set()
            return

        logger.info("Initiating graceful shutdown...")
        self.running = False  # Mark as not running early

        # 1. Stop accepting new connections (handled by AppRunner cleanup later)

        # 2. Clean up sessions/simulators managed by this pod
        await self._cleanup_pod_sessions()

        # 3. Unregister pod from service discovery (Redis)
        if self.db_manager.redis:
            try:
                logger.info(f"Unregistering pod '{config.kubernetes.pod_name}' from Redis.")
                await self.db_manager.redis.srem("active_pods", config.kubernetes.pod_name)
                await self.db_manager.redis.publish("session_events", json.dumps({
                    'type': 'pod_offline',
                    'pod_name': config.kubernetes.pod_name,
                    'timestamp': time.time()
                }))
            except Exception as e:
                logger.error(f"Error unregistering pod from Redis: {e}", exc_info=True)

        # 4. Cancel background tasks (Pub/Sub listener)
        if self.pubsub_task and not self.pubsub_task.done():
            logger.info("Cancelling Redis pub/sub listener task...")
            self.pubsub_task.cancel()
            try:
                await asyncio.wait_for(self.pubsub_task, timeout=2.0)  # Give it time to clean up
            except asyncio.CancelledError:
                logger.info("Pub/sub listener task successfully cancelled.")
            except asyncio.TimeoutError:
                logger.warning("Pub/sub listener task did not finish cancelling within timeout.")
            except Exception as e:
                logger.error(f"Error waiting for pub/sub task cancellation: {e}", exc_info=True)

        # 5. Stop session manager tasks (Cleanup task)
        if self.session_manager:
            logger.info("Stopping session manager cleanup task...")
            await self.session_manager.stop_cleanup_task()

        # 6. Close WebSocket connections
        if self.websocket_manager:
            logger.info("Closing all WebSocket connections...")
            await self.websocket_manager.close_all_connections("Server is shutting down")

        # 7. Close external connections (API clients, Redis, DB)
        if self.auth_client: await self.auth_client.close()
        if self.exchange_client: await self.exchange_client.close()
        if self.db_manager.redis: await self.db_manager.redis.close()  # Close the main connection pool
        if self.db_manager: await self.db_manager.close()
        logger.info("Closed external connections (Clients, Redis, DB).")

        # 8. Stop the AppRunner (stops accepting connections and cleans up sites)
        if self._runner:
            logger.info("Cleaning up aiohttp AppRunner...")
            await self._runner.cleanup()
            logger.info("AppRunner cleanup complete.")

        logger.info("Server shutdown sequence finished.")
        self.shutdown_event.set()  # Signal that shutdown is complete

    async def _handle_signal(self, sig):
        """Handle termination signals."""
        logger.warning(f"Received signal {sig.name}. Initiating shutdown...")
        # Prevent double shutdown calls if signal received multiple times quickly
        if not self.shutdown_event.is_set() and self.running:
            await self.shutdown()
        else:
            logger.info("Shutdown already in progress or server not running.")

    async def health_check(self, request):
        """Simple liveness check endpoint"""
        # Basic check: if this handler runs, the server process is alive
        return web.json_response({
            'status': 'UP',
            'timestamp': time.time(),
            'pod': config.kubernetes.pod_name
        })

    async def readiness_check(self, request):
        """Comprehensive readiness check for dependencies"""
        checks = {}
        all_ready = True

        # Check DB connection
        if self.db_manager:
            db_ready = await self.db_manager.check_connection()
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

    async def metrics_endpoint(self, request):
        """Prometheus metrics endpoint"""
        # generate_latest needs to be called within the handler
        try:
            metrics_data = generate_latest()
            return web.Response(
                body=metrics_data,
                content_type=CONTENT_TYPE_LATEST
            )
        except Exception as e:
            logger.error(f"Error generating Prometheus metrics: {e}", exc_info=True)
            return web.Response(status=500, text="Error generating metrics")

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

        # Apply CORS to all routes
        for route in list(self.app.router.routes()):
            # Skip WebSocket routes as CORS doesn't apply directly
            # Health/metrics endpoints might not need CORS depending on setup
            # path = route.resource.canonical if hasattr(route.resource, 'canonical') else str(route.resource)
            # if path != '/ws': # Example exclusion
            try:
                cors.add(route)
            except ValueError:
                # Might happen if route already has CORS via other means, log if needed
                # logger.warning(f"Could not add CORS to route: {route.method} {path}")
                pass

    async def _cleanup_pod_sessions(self):
        """Clean up sessions and simulators associated with this pod before shutdown"""
        logger.info("Starting cleanup of sessions managed by this pod.")
        if not self.session_manager or not self.db_manager:
            logger.error("Session Manager or DB Manager not available for cleanup.")
            return

        try:
            # Get all active sessions potentially managed by this pod
            # A better approach might be to query sessions explicitly marked with this pod_name
            # For now, let's assume session_manager knows which ones are local or needs a method
            # This part needs refinement based on how sessions are tracked per pod.
            # Using the original query for now:
            pod_sessions: List[Any] = await self.db_manager.get_sessions_with_criteria({
                'pod_name': config.kubernetes.pod_name
                # Add 'status': 'active' or similar if applicable
            })

            if not pod_sessions:
                logger.info("No active sessions found for this pod to clean up.")
                return

            logger.info(f"Found {len(pod_sessions)} sessions potentially managed by this pod. Initiating cleanup...")

            # Process simulators in parallel for faster shutdown
            simulator_tasks = []
            sessions_to_update = []

            for session_data in pod_sessions:
                # Access metadata safely, assuming it might be None or not a dict
                metadata = getattr(session_data, 'metadata', {})
                if not isinstance(metadata, dict): metadata = {}

                session_id = getattr(session_data, 'session_id', None)
                if not session_id: continue  # Skip if no session ID found

                simulator_id = metadata.get('simulator_id')
                simulator_status = metadata.get('simulator_status')
                simulator_endpoint = metadata.get('simulator_endpoint')

                sessions_to_update.append(session_id)

                # Check if session has a simulator running or starting
                if simulator_id and simulator_status not in [SimulatorStatus.STOPPED.value, SimulatorStatus.ERROR.value,
                                                             None]:
                    logger.info(f"Scheduling simulator {simulator_id} for session {session_id} for shutdown.")
                    # Create task to stop simulator using fallbacks
                    task = asyncio.create_task(
                        self._stop_simulator_with_fallbacks(
                            session_id,
                            simulator_id,
                            simulator_endpoint
                        )
                    )
                    simulator_tasks.append(task)
                else:
                    logger.debug(f"No active simulator found for session {session_id} to stop.")

            # Wait for simulator shutdowns with timeout
            if simulator_tasks:
                logger.info(f"Waiting for {len(simulator_tasks)} simulator shutdown tasks...")
                # Allow timeout for graceful shutdowns
                done, pending = await asyncio.wait(
                    simulator_tasks,
                    timeout=config.server.shutdown_timeout - 2.0,  # Allow margin
                    return_when=asyncio.ALL_COMPLETED
                )

                logger.info(f"Completed {len(done)} simulator shutdown tasks.")
                if pending:
                    logger.warning(f"{len(pending)} simulator shutdown tasks timed out or were cancelled.")
                    # Cancel any pending tasks explicitly
                    for task in pending:
                        task.cancel()
                        try:
                            await task  # Allow cancellation to propagate
                        except asyncio.CancelledError:
                            pass
                        except Exception as e:
                            logger.error(f"Error awaiting cancelled simulator task: {e}", exc_info=True)
                    # Optionally add direct K8s delete here for timed-out ones if needed

            # Update all affected session states in DB
            logger.info(f"Updating metadata for {len(sessions_to_update)} sessions to mark pod termination.")
            update_metadata = {
                'pod_terminating': True,
                'termination_time': time.time(),
                # Mark simulator as stopped if we attempted cleanup, even if it failed/timed out
                # K8s garbage collection should handle orphaned resources eventually
                'simulator_status': SimulatorStatus.STOPPED.value
            }

            # Batch update sessions if DB manager supports it, otherwise loop
            for s_id in sessions_to_update:
                try:
                    await self.db_manager.update_session_metadata(s_id, update_metadata)

                    # Notify clients via WebSocket that they should reconnect
                    if self.websocket_manager:
                        await self.websocket_manager.broadcast_to_session(
                            s_id,
                            {
                                'type': 'pod_terminating',
                                'message': 'Service instance is shutting down, please reconnect'
                            }
                        )
                except Exception as e:
                    logger.error(f"Error updating session {s_id} metadata during shutdown: {e}", exc_info=True)

            logger.info("Session cleanup phase complete.")

        except Exception as e:
            logger.error(f"Error during _cleanup_pod_sessions: {e}", exc_info=True)

    async def _stop_simulator_with_fallbacks(self, session_id: str, simulator_id: str,
                                             simulator_endpoint: Optional[str]):
        """Attempt to stop simulator via gRPC, fallback to K8s delete."""
        logger.debug(f"Attempting graceful stop for simulator {simulator_id} (Session: {session_id})")

        # Ensure clients are available
        if not self.exchange_client or not self.session_manager or not getattr(self.session_manager, 'k8s_client',
                                                                               None):
            logger.error("Required clients (Exchange, K8s) not available for simulator stop.")
            return False

        # Strategy 1: Try gRPC call if endpoint is available
        if simulator_endpoint:
            try:
                logger.debug(f"Using gRPC endpoint {simulator_endpoint} to stop simulator {simulator_id}")
                logger.info(f"Successfully stopped simulator {simulator_id} via gRPC")
                return True
            except Exception as e:
                logger.warning(f"Error calling stop_simulator via gRPC for {simulator_id}: {e}")

        # Strategy 2: Delete K8s resources directly if gRPC failed or wasn't possible
        logger.warning(f"Falling back to K8s resource deletion for simulator {simulator_id}")
        try:
            await self.session_manager.k8s_client.delete_simulator_deployment(simulator_id)
            logger.info(f"Successfully deleted K8s resources for simulator {simulator_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete K8s resources for simulator {simulator_id}: {e}", exc_info=True)
            return False

    async def wait_for_shutdown(self):
        """Wait until the shutdown process is complete."""
        logger.info("Server running. Waiting for shutdown signal...")
        await self.shutdown_event.wait()
        logger.info("Shutdown signal received and processed. Exiting wait.")
