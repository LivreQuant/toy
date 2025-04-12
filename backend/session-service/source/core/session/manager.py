"""
Session manager for handling user sessions.
Coordinates the core components for session management.
"""
import logging
import asyncio

from opentelemetry import trace

from source.config import config

from source.utils.event_bus import event_bus

from source.db.manager import StoreManager

from source.clients.auth import AuthClient
from source.clients.exchange import ExchangeClient

from source.core.stream.manager import StreamManager
from source.core.simulator.manager import SimulatorManager

from source.core.session.session_operations import SessionOperations
from source.core.session.simulator_operations import SimulatorOperations
from source.core.session.connection import Connection
from source.core.session.tasks import Tasks


logger = logging.getLogger('session_manager')


class SessionManager:
    """Manager for user sessions - coordinates all session-related operations"""

    def __init__(
            self,
            store_manager: StoreManager,
            exchange_client: ExchangeClient,
            stream_manager: StreamManager,
            simulator_manager: SimulatorManager,
    ):
        """
        Initialize session manager and its component modules

        Args:
            store_manager: PostgreSQL store for session persistence
            exchange_client: Exchange client for simulator communication
            simulator_manager: Manager for simulator operations
            stream_manager: Stream manager for managing background streams
        """
        self.store_manager = store_manager
        self.exchange_client = exchange_client
        self.stream_manager = stream_manager
        self.simulator_manager = simulator_manager

        # Initialize component modules
        self.session_ops = SessionOperations(self)
        self.simulator_ops = SimulatorOperations(self)
        self.connection = Connection(self)
        self.tasks = Tasks(self)

        # Background tasks
        self.cleanup_task = None
        self.heartbeat_task = None

        # Create tracer
        self.tracer = trace.get_tracer("session_manager")

        # Subscribe to events
        event_bus.subscribe('stream_error', self.handle_stream_error)

        logger.info("Session manager initialized")

    # ----- Public API methods -----

    async def create_session(self, user_id, device_id, ip_address=None):
        """Create a new session or return existing one"""
        session_id, is_new = await self.session_ops.create_session(user_id, device_id, ip_address)
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

    async def validate_session(self, session_id, user_id, device_id=None):
        """Validate session ownership"""
        return await self.session_ops.validate_session(session_id, user_id, device_id)

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

    async def end_session(self, session_id, user_id):
        """End a session and clean up resources"""
        success, error = await self.session_ops.end_session(session_id, user_id)
        if success:
            # Publish event that session was ended
            await event_bus.publish('session_ended', session_id=session_id)
        return success, error

    async def update_connection_quality(self, session_id, user_id, metrics):
        """Update connection quality metrics"""
        quality, reconnect_recommended = await self.connection.update_connection_quality(session_id, user_id, metrics)
        # Publish event with connection quality update
        await event_bus.publish('connection_quality_updated',
                                session_id=session_id,
                                quality=quality,
                                reconnect_recommended=reconnect_recommended)
        return quality, reconnect_recommended

    async def reconnect_session(self, session_id, user_id, device_id, attempt=1):
        """Handle session reconnection"""
        session_data, error = await self.connection.reconnect_session(session_id, user_id, device_id, attempt)
        if session_data:
            # Publish event that session was reconnected
            await event_bus.publish('session_reconnected',
                                    session_id=session_id,
                                    device_id=device_id,
                                    attempt=attempt)
        return session_data, error

    async def session_exists(self, session_id):
        """Check if a session exists"""
        session = await self.store_manager.session_store.get_session_from_db(session_id, skip_activity_check=True)
        return session is not None

    # ----- Simulator operations - delegated to SimulatorOperations -----

    async def start_simulator(self, session_id, user_id):
        """Start a simulator for a session"""
        # Delegate to simulator operations
        simulator, error = await self.simulator_ops.create_simulator(session_id, user_id)

        if simulator and not error:
            # Start exchange stream if simulator created successfully
            try:
                # Create the exchange data stream task
                stream_task = asyncio.create_task(
                    self._stream_simulator_data(session_id, simulator['endpoint'])
                )

                # Register with stream manager
                if stream_task and self.stream_manager:
                    self.stream_manager.register_stream(session_id, stream_task)

                # Publish event that simulator was started
                await event_bus.publish('simulator_started',
                                        session_id=session_id,
                                        simulator_id=simulator['simulator_id'],
                                        endpoint=simulator['endpoint'])

            except Exception as e:
                logger.error(f"Failed to start exchange stream: {e}", exc_info=True)

            return simulator['simulator_id'], simulator['endpoint'], ""

        return None, None, error

    async def _stream_simulator_data(self, session_id: str, endpoint: str):
        """
        Wrapper method for streaming simulator data
        Allows for additional logging and error handling
        """
        try:
            async for data in self.simulator_ops.stream_exchange_data(session_id, endpoint):
                await event_bus.publish('exchange_data_received',
                                        session_id=session_id,
                                        data=data)
        except Exception as e:
            logger.error(f"Error in simulator data streaming for session {session_id}: {e}")
            await event_bus.publish('stream_failed',
                                    session_id=session_id,
                                    error=str(e))

    async def stop_simulator(self, session_id, force=False):
        """Stop a simulator for a session"""
        # Get session to find simulator
        session = await self.store_manager.session_store.get_session_from_db(session_id, skip_activity_check=force)
        if not session:
            return False, "Session not found"

        # Extract simulator details from metadata
        metadata = session.metadata
        simulator_id = getattr(metadata, 'simulator_id', None)

        if not simulator_id:
            return True, ""

        # Delegate to simulator operations
        success, error = await self.simulator_ops.stop_simulator(session_id, force)

        # Update session metadata
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
            self.heartbeat_task = asyncio.create_task(self.simulator_ops.run_simulator_heartbeat_loop())
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
        pod_name = pod_name or config.kubernetes.pod_name
        return await self.tasks.cleanup_pod_sessions(pod_name)
