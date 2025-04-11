"""
Session manager for handling user sessions.
Coordinates the core components for session management.
"""
import logging
import asyncio
import random

from opentelemetry import trace

from source.config import config
from source.utils.event_bus import event_bus

from source.db.manager import StoreManager

from source.api.clients.auth_client import AuthClient
from source.api.clients.exchange_client import ExchangeClient

from source.core.session.operations import SessionOperations
from source.core.session.connection_utils import ConnectionUtils
from source.core.session.tasks import SessionTasks

from source.core.stream.manager import StreamManager
from source.core.simulator.manager import SimulatorManager

from source.models.session import SessionStatus
from source.models.simulator import SimulatorStatus

logger = logging.getLogger('session_manager')


class SessionManager:
    """Manager for user sessions - coordinates all session-related operations"""

    def __init__(
            self,
            store_manager: StoreManager,
            auth_client: AuthClient,
            exchange_client: ExchangeClient,
            stream_manager: StreamManager,
            simulator_manager: SimulatorManager,
    ):
        """
        Initialize session manager and its component modules

        Args:
            store_manager: PostgreSQL store for session persistence
            auth_client: Authentication client for token validation
            exchange_client: Exchange client for simulator communication
            simulator_manager: Manager for simulator operations
            stream_manager: Stream manager for managing background streams
        """
        self.store_manager = store_manager

        self.auth_client = auth_client
        self.exchange_client = exchange_client
        self.stream_manager = stream_manager
        self.simulator_manager = simulator_manager

        # Initialize component modules
        self.session_ops = SessionOperations(self)
        self.connection_utils = ConnectionUtils(self)
        self.tasks = SessionTasks(self)

        # Background tasks
        self.cleanup_task = None
        self.heartbeat_task = None

        # Create tracer
        self.tracer = trace.get_tracer("session_manager")

        # Subscribe to events
        event_bus.subscribe('stream_error', self.handle_stream_error)

        logger.info("Session manager initialized")

    # ----- Public API methods -----

    async def create_session(self, user_id, device_id, token, ip_address=None):
        """Create a new session or return existing one"""
        session_id, is_new = await self.session_ops.create_session(user_id, device_id, token, ip_address)
        if session_id and is_new:
            # Publish event that new session was created
            await event_bus.publish('session_created',
                                    session_id=session_id,
                                    user_id=user_id,
                                    device_id=device_id)
        return session_id, is_new

    async def get_session(self, session_id):
        """Get session by ID"""
        return await self.session_ops.get_session(session_id)

    async def validate_session(self, session_id, token, device_id=None):
        """Validate session ownership"""
        return await self.session_ops.validate_session(session_id, token, device_id)

    async def update_session_activity(self, session_id):
        """Update session last activity time"""
        success = await self.session_ops.update_session_activity(session_id)
        if success:
            # Publish event that session activity was updated
            await event_bus.publish('session_activity_updated', session_id=session_id)
        return success

    async def update_session_metadata(self, session_id, metadata_updates):
        """Update session metadata"""
        success = await self.store_manager.session_store.update_session_metadata(session_id, metadata_updates)
        if success:
            # Publish event that metadata was updated
            await event_bus.publish('session_metadata_updated',
                                    session_id=session_id,
                                    updates=metadata_updates)
        return success

    async def end_session(self, session_id, token):
        """End a session and clean up resources"""
        success, error = await self.session_ops.end_session(session_id, token)
        if success:
            # Publish event that session was ended
            await event_bus.publish('session_ended', session_id=session_id)
        return success, error

    async def update_connection_quality(self, session_id, token, metrics):
        """Update connection quality metrics"""
        quality, reconnect_recommended = await self.connection_utils.update_connection_quality(session_id, token,
                                                                                               metrics)
        # Publish event with connection quality update
        await event_bus.publish('connection_quality_updated',
                                session_id=session_id,
                                quality=quality,
                                reconnect_recommended=reconnect_recommended)
        return quality, reconnect_recommended

    async def reconnect_session(self, session_id, token, device_id, attempt=1):
        """Handle session reconnection"""
        session_data, error = await self.connection_utils.reconnect_session(session_id, token, device_id, attempt)
        if session_data:
            # Publish event that session was reconnected
            await event_bus.publish('session_reconnected',
                                    session_id=session_id,
                                    device_id=device_id,
                                    attempt=attempt)
        return session_data, error

    async def get_user_from_token(self, token):
        """Extract user ID from token"""
        return await self.session_ops.get_user_from_token(token)

    async def session_exists(self, session_id):
        """Check if a session exists"""
        session = await self.store_manager.session_store.get_session_from_db(session_id, skip_activity_check=True)
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
                # Create the exchange data stream task
                stream_task = await self._create_exchange_stream_task(session_id, simulator.endpoint)

                # Register with stream manager if available
                if stream_task and self.stream_manager:
                    self.stream_manager.register_stream(session_id, stream_task)

                # Publish event that simulator was started
                await event_bus.publish('simulator_started',
                                        session_id=session_id,
                                        simulator_id=simulator.simulator_id,
                                        endpoint=simulator.endpoint)

            except Exception as e:
                logger.error(f"Failed to start exchange stream: {e}", exc_info=True)

            return simulator.simulator_id, simulator.endpoint, ""

        return None, None, error

    async def stop_simulator(self, session_id, token, force=False):
        """Stop a simulator for a session"""
        if not self.simulator_manager:
            return False, "Simulator manager not available"

        if not force:
            user_id = await self.validate_session(session_id, token)
            if not user_id:
                return False, "Invalid session or token"

            # Get session to find simulator
        session = await self.store_manager.session_store.get_session_from_db(session_id, skip_activity_check=force)
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

        # Publish event that simulator was stopped
        if success:
            await event_bus.publish('simulator_stopped',
                                    session_id=session_id,
                                    simulator_id=simulator_id)

        return success, error

    async def _create_exchange_stream_task(self, session_id, endpoint):
        """Create a task for exchange data streaming without starting it"""
        if not self.exchange_client:
            logger.error("Exchange client not available")
            return None

        logger.info(f"Creating exchange stream task for session {session_id} to endpoint {endpoint}")

        # Create a named task for the stream
        stream_task = asyncio.create_task(
            self._stream_exchange_data(session_id, endpoint),
            name=f"exchange-stream-{session_id}"
        )

        return stream_task

    async def _stream_exchange_data(self, session_id, endpoint):
        """Background task for streaming exchange data and publishing events"""
        max_attempts = 5
        base_delay = 1  # Initial delay in seconds
        max_delay = 30  # Maximum delay between attempts

        # Update session metadata to indicate streaming is starting
        await self.update_session_metadata(session_id, {
            'simulator_status': 'STARTING',
            'simulator_endpoint': endpoint
        })

        for attempt in range(max_attempts):
            try:
                # Get session details
                session = await self.store_manager.session_store.get_session_from_db(session_id)

                if not session:
                    logger.error(f"No session found for {session_id}")
                    return

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

                    # Update metadata to indicate streaming is running
                    await self.update_session_metadata(session_id, {
                        'simulator_status': 'RUNNING'
                    })

                    # Publish event that simulator is ready
                    await event_bus.publish('simulator_ready',
                                            session_id=session_id,
                                            endpoint=endpoint)

                    # Start continuous streaming
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

                                # Publish event with exchange data
                                await event_bus.publish('exchange_data_received',
                                                        session_id=session_id,
                                                        data=data)

                        except Exception as stream_error:
                            stream_attempts += 1
                            stream_delay = min(base_delay * (2 ** stream_attempts) + random.uniform(0, 1),
                                               max_delay)

                            logger.warning(
                                f"Stream connection attempt {stream_attempts} failed. "
                                f"Error: {stream_error}. "
                                f"Waiting {stream_delay:.2f}s before retry"
                            )

                            # Publish event about stream error
                            await event_bus.publish('stream_error',
                                                    session_id=session_id,
                                                    error=str(stream_error),
                                                    attempt=stream_attempts,
                                                    max_attempts=max_stream_attempts)

                            # Update simulator status for persistent errors
                            if stream_attempts >= max_stream_attempts:
                                logger.error(f"Exceeded max stream connection attempts for session {session_id}")
                                await self.update_session_metadata(session_id, {
                                    'simulator_status': 'ERROR'
                                })

                                # Publish terminal error event
                                await event_bus.publish('stream_failed',
                                                        session_id=session_id,
                                                        error="Max connection attempts reached")
                                break

                            await asyncio.sleep(stream_delay)

                    # If we exit the loop, the stream has failed permanently
                    return

                # If heartbeat fails, log and continue to next attempt
                logger.warning(f"Heartbeat failed for session {session_id} (Attempt {attempt + 1})")

                # Publish heartbeat failure event
                await event_bus.publish('simulator_heartbeat_failed',
                                        session_id=session_id,
                                        attempt=attempt + 1,
                                        max_attempts=max_attempts)

                # On final attempt, mark as error
                if attempt == max_attempts - 1:
                    await self.update_session_metadata(session_id, {
                        'simulator_status': 'ERROR'
                    })

                    # Publish final failure event
                    await event_bus.publish('simulator_connection_failed',
                                            session_id=session_id,
                                            error="Failed to establish connection")
                    return

            except Exception as e:
                logger.error(f"Error in exchange stream initialization (Attempt {attempt + 1}): {e}")

                # Publish general error event
                await event_bus.publish('stream_error',
                                        session_id=session_id,
                                        error=str(e),
                                        attempt=attempt + 1,
                                        max_attempts=max_attempts)

                # On final attempt, mark as error
                if attempt == max_attempts - 1:
                    await self.update_session_metadata(session_id, {
                        'simulator_status': 'ERROR'
                    })

                    # Publish final failure event
                    await event_bus.publish('simulator_connection_failed',
                                            session_id=session_id,
                                            error=str(e))
                    return

        # If all attempts fail
        logger.error(f"All attempts to connect to simulator for session {session_id} failed")

    async def handle_stream_error(self, session_id, error, attempt=None, max_attempts=None):
        """Handle stream error events"""
        # Update session metadata to reflect error state if this is a terminal error
        if attempt is not None and max_attempts is not None and attempt >= max_attempts:
            await self.update_session_metadata(session_id, {
                'simulator_status': 'ERROR',
                'simulator_error': error
            })

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

















