"""
Session manager for handling user sessions.
Coordinates the core components for session management.
"""
import logging
import asyncio
import random

from opentelemetry import trace

from source.config import config

from source.db.manager import StoreManager

from source.api.clients.auth_client import AuthClient
from source.api.clients.exchange_client import ExchangeClient

from source.core.session.operations import SessionOperations
from source.core.session.connection_utils import ConnectionUtils
from source.core.session.tasks import SessionTasks

logger = logging.getLogger('session_manager')


class SessionManager:
    """Manager for user sessions - coordinates all session-related operations"""

    def __init__(
            self,
            store: StoreManager,
            auth_client: AuthClient = None,
            exchange_client: ExchangeClient = None,
            simulator_manager=None,
            websocket_manager=None,
            stream_manager=None
    ):
        """
        Initialize session manager and its component modules

        Args:
            postgres_store: PostgreSQL store for session persistence
            auth_client: Authentication client for token validation
            exchange_client: Exchange client for simulator communication
            simulator_manager: Manager for simulator operations
            websocket_manager: WebSocket manager for client notifications
            stream_manager: Stream manager for managing background streams
        """
        self.store = store

        self.auth_client = auth_client
        self.exchange_client = exchange_client
        self.simulator_manager = simulator_manager
        self.websocket_manager = websocket_manager
        self.stream_manager = stream_manager

        self.pod_name = config.kubernetes.pod_name

        # Initialize component modules
        self.session_ops = SessionOperations(self)
        self.connection_utils = ConnectionUtils(self)
        self.tasks = SessionTasks(self)

        # Background tasks
        self.cleanup_task = None
        self.heartbeat_task = None

        # Create tracer
        self.tracer = trace.get_tracer("session_manager")

        logger.info("Session manager initialized")

    # ----- Public API methods -----

    async def create_session(self, user_id, device_id, token, ip_address=None):
        """Create a new session or return existing one"""
        return await self.session_ops.create_session(user_id, device_id, token, ip_address)

    async def get_session(self, session_id):
        """Get session by ID"""
        return await self.session_ops.get_session(session_id)

    async def validate_session(self, session_id, token, device_id=None):
        """Validate session ownership"""
        return await self.session_ops.validate_session(session_id, token, device_id)

    async def update_session_activity(self, session_id):
        """Update session last activity time"""
        return await self.session_ops.update_session_activity(session_id)

    async def update_session_metadata(self, session_id, metadata_updates):
        """Update session metadata"""
        return await self.postgres_store.update_session_metadata(session_id, metadata_updates)

    async def end_session(self, session_id, token):
        """End a session and clean up resources"""
        return await self.session_ops.end_session(session_id, token)

    async def update_connection_quality(self, session_id, token, metrics):
        """Update connection quality metrics"""
        return await self.connection_utils.update_connection_quality(session_id, token, metrics)

    async def reconnect_session(self, session_id, token, device_id, attempt=1):
        """Handle session reconnection"""
        return await self.connection_utils.reconnect_session(session_id, token, device_id, attempt)

    async def get_user_from_token(self, token):
        """Extract user ID from token"""
        return await self.session_ops.get_user_from_token(token)

    async def session_exists(self, session_id):
        """Check if a session exists"""
        session = await self.postgres_store.get_session_from_db(session_id, skip_activity_check=True)
        return session is not None

    # ----- Simulator operations - delegated to SimulatorManager -----

    async def start_simulator(self, session_id, token):
        """Start a simulator for a session"""
        if not self.simulator_manager:
            return None, None, "Simulator manager not available"

        # First validate the session
        user_id = await self.validate_session(session_id, token)
        if not user_id:
            return None, None, "Invalid session or token"

        # Delegate to simulator manager
        simulator, error = await self.simulator_manager.create_simulator(session_id, user_id)

        if simulator and not error:
            # Start exchange stream if simulator created successfully
            try:
                stream_task = await self._start_exchange_stream(session_id, simulator.endpoint)
                if stream_task and self.stream_manager:
                    self.stream_manager.register_stream(session_id, stream_task)
            except Exception as e:
                logger.error(f"Failed to start exchange stream: {e}", exc_info=True)

            return simulator.simulator_id, simulator.endpoint, ""

        return None, None, error

    async def stop_simulator(self, session_id, token, force=False):
        """Stop a simulator for a session"""
        if not self.simulator_manager:
            return False, "Simulator manager not available"

        # Validate session (unless forcing)
        if not force:
            user_id = await self.validate_session(session_id, token)
            if not user_id:
                return False, "Invalid session or token"

        # Get session to find simulator
        session = await self.postgres_store.get_session_from_db(session_id, skip_activity_check=force)
        if not session:
            return False, "Session not found"

        # Extract simulator ID from metadata
        metadata = session.metadata
        simulator_id = getattr(metadata, 'simulator_id', None)

        if not simulator_id:
            # No simulator to stop
            return True, ""

        # Delegate to simulator manager
        success, error = await self.simulator_manager.stop_simulator(simulator_id)

        # Update session metadata regardless of success
        # This ensures clients won't try to reconnect to a problematic simulator
        await self.update_session_metadata(session_id, {
            'simulator_status': 'STOPPED',
            'simulator_id': None,
            'simulator_endpoint': None
        })

        return success, error

    async def _start_exchange_stream(self, session_id, endpoint):
        """Start an exchange data stream for a session"""
        if not self.exchange_client:
            logger.error("Exchange client not available")
            return None

        logger.info(f"Starting exchange stream for session {session_id} to endpoint {endpoint}")

        max_attempts = 5
        base_delay = 1  # Initial delay in seconds
        max_delay = 30  # Maximum delay between attempts

        for attempt in range(max_attempts):
            try:
                # Get session details
                session = await self.postgres_store.get_session_from_db(session_id)

                if not session:
                    logger.error(f"No session found for {session_id}")
                    return None

                # Exponential backoff calculation
                delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)

                # First, send a heartbeat to verify the simulator is ready
                logger.info(f"Attempting heartbeat (Attempt {attempt + 1}): Delay {delay:.2f}s")
                await asyncio.sleep(delay)  # Backoff before retry

                heartbeat_result = await self.exchange_client.send_heartbeat(
                    endpoint,
                    session_id,
                    f"stream-init-{session_id}"
                )

                # Check heartbeat success
                if heartbeat_result.get('success', False):
                    logger.info(f"Heartbeat successful for session {session_id}")

                    # Create streaming task
                    async def stream_and_broadcast():
                        stream_attempts = 0
                        max_stream_attempts = 5

                        while stream_attempts < max_stream_attempts:
                            try:
                                async for data in self.exchange_client.stream_exchange_data(
                                        endpoint,
                                        session_id,
                                        f"stream-{session_id}"
                                ):
                                    # Reset stream attempts on successful connection
                                    stream_attempts = 0

                                    # Broadcast to all WebSocket clients for this session
                                    if self.websocket_manager:
                                        await self.websocket_manager.broadcast_to_session(session_id, {
                                            'type': 'exchange_data',
                                            'data': data
                                        })

                            except Exception as stream_error:
                                stream_attempts += 1
                                stream_delay = min(base_delay * (2 ** stream_attempts) + random.uniform(0, 1),
                                                   max_delay)

                                logger.warning(
                                    f"Stream connection attempt {stream_attempts} failed. "
                                    f"Error: {stream_error}. "
                                    f"Waiting {stream_delay:.2f}s before retry"
                                )

                                # Update simulator status for persistent errors
                                if stream_attempts >= max_stream_attempts:
                                    logger.error(f"Exceeded max stream connection attempts for session {session_id}")
                                    await self.postgres_store.update_session_metadata(session_id, {
                                        'simulator_status': 'ERROR'
                                    })
                                    break

                                await asyncio.sleep(stream_delay)

                    # Start the streaming task
                    return asyncio.create_task(stream_and_broadcast())

                # If heartbeat fails, log and continue to next attempt
                logger.warning(f"Heartbeat failed for session {session_id} (Attempt {attempt + 1})")

                # On final attempt, mark as error
                if attempt == max_attempts - 1:
                    await self.postgres_store.update_session_metadata(session_id, {
                        'simulator_status': 'ERROR'
                    })
                    return None

            except Exception as e:
                logger.error(f"Error in exchange stream initialization (Attempt {attempt + 1}): {e}")

                # On final attempt, mark as error
                if attempt == max_attempts - 1:
                    await self.postgres_store.update_session_metadata(session_id, {
                        'simulator_status': 'ERROR'
                    })
                    return None

        # If all attempts fail
        return None

    # ----- Background tasks -----

    async def start_session_tasks(self):
        """Start background cleanup task and simulator heartbeat task"""
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self.tasks.run_cleanup_loop())
            logger.info("Started session cleanup task")

        if self.heartbeat_task is None or self.heartbeat_task.done():
            self.heartbeat_task = asyncio.create_task(self.tasks.run_simulator_heartbeat_loop())
            logger.info("Started simulator heartbeat task")

    async def stop_cleanup_task(self):
        """Stop background cleanup task and heartbeat task"""
        logger.info("Stopping background tasks (cleanup, heartbeat)...")

        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                logger.info("Session cleanup task cancelled")
            except Exception as e:
                logger.error(f"Error awaiting cancelled cleanup task: {e}")
            self.cleanup_task = None

        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                logger.info("Simulator heartbeat task cancelled")
            except Exception as e:
                logger.error(f"Error awaiting cancelled heartbeat task: {e}")
            self.heartbeat_task = None

        logger.info("Background tasks stopped")

    async def cleanup_pod_sessions(self, pod_name=None):
        """Clean up sessions associated with a pod before shutdown"""
        pod_name = pod_name or self.pod_name
        return await self.tasks.cleanup_pod_sessions(pod_name)
