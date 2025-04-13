"""
Session manager for handling a single user session.
Coordinates the core components for session management.
"""
import logging
import asyncio
from typing import Optional, Dict, Any

from opentelemetry import trace

from source.utils.event_bus import event_bus

from source.db.manager import StoreManager

from source.clients.exchange import ExchangeClient

from source.core.stream.manager import StreamManager
from source.core.simulator.manager import SimulatorManager

from source.core.session.simulator_operations import SimulatorOperations
from source.core.session.connection import Connection

logger = logging.getLogger('session_manager')


async def validate_session(user_id):
    """
    Validate session ownership - always validates successfully in singleton mode
    """
    return user_id


class SessionManager:
    """Manager for a single user session - coordinates all session-related operations"""

    def __init__(
            self,
            store_manager: StoreManager,
            exchange_client: ExchangeClient,
            stream_manager: StreamManager,
            simulator_manager: SimulatorManager,
            session_id: str
    ):
        """
        Initialize session manager with a pre-defined session ID

        Args:
            store_manager: PostgreSQL store for session persistence
            exchange_client: Exchange client for simulator communication
            simulator_manager: Manager for simulator operations
            stream_manager: Stream manager for managing background streams
            session_id: The predefined session ID to use
        """
        self.store_manager = store_manager
        self.exchange_client = exchange_client
        self.stream_manager = stream_manager
        self.simulator_manager = simulator_manager

        # Session identifier
        self.session_id = session_id

        # Initialize component modules
        self.simulator_ops = SimulatorOperations(self)
        self.connection = Connection(self)

        # Connection tracking
        self.frontend_connections = 0

        # Create tracer
        self.tracer = trace.get_tracer("session_manager")

        logger.info(f"Session manager initialized with session ID: {session_id}")

    # ----- Public API methods -----

    async def get_session(self):
        """Get the current session"""
        return await self.store_manager.session_store.get_session_from_db(self.session_id)

    async def get_session_metadata(self) -> Optional[Dict[str, Any]]:
        """Get session metadata as a dictionary"""
        session = await self.get_session()
        if not session or not hasattr(session, 'metadata'):
            return None

        # Convert the SessionMetadata object to a dictionary
        try:
            return session.metadata.dict()
        except Exception as e:
            logger.error(f"Error converting session metadata to dict: {e}")
            return {}

    async def update_session_activity(self):
        """Update session last activity time"""
        success = await self.store_manager.session_store.update_session_activity(self.session_id)
        if success:
            # Publish event that session activity was updated
            await event_bus.publish('session_activity_updated', session_id=self.session_id)
        return success

    async def update_session_metadata(self, metadata_updates):
        """Update session metadata"""
        success = await self.store_manager.session_store.update_session_metadata(self.session_id, metadata_updates)
        if success:
            # Publish event that metadata was updated
            await event_bus.publish('session_metadata_updated',
                                    session_id=self.session_id,
                                    updates=metadata_updates)
        return success

    # ----- Simulator operations -----

    async def start_simulator(self, user_id=None):
        """Start a simulator for the session"""
        # Delegate to simulator operations
        simulator, error = await self.simulator_ops.create_simulator(self.session_id, user_id or "default-user")

        if simulator and not error:
            # Start exchange stream if simulator created successfully
            try:
                # Create the exchange data stream task
                stream_task = asyncio.create_task(
                    self._stream_simulator_data(simulator['endpoint'])
                )

                # Register with stream manager
                if stream_task and self.stream_manager:
                    self.stream_manager.register_stream(self.session_id, stream_task)

                # Publish event that simulator was started
                await event_bus.publish('simulator_started',
                                        session_id=self.session_id,
                                        simulator_id=simulator['simulator_id'],
                                        endpoint=simulator['endpoint'])

            except Exception as e:
                logger.error(f"Failed to start exchange stream: {e}", exc_info=True)

            return simulator['simulator_id'], simulator['endpoint'], ""

        return None, None, error

    async def _stream_simulator_data(self, endpoint: str):
        """Stream simulator data"""
        try:
            async for data in self.simulator_ops.stream_exchange_data(endpoint):
                await event_bus.publish('exchange_data_received',
                                        session_id=self.session_id,
                                        data=data)
        except Exception as e:
            logger.error(f"Error in simulator data streaming: {e}")
            await event_bus.publish('stream_failed',
                                    session_id=self.session_id,
                                    error=str(e))

    async def stop_simulator(self, force=False):
        """Stop the simulator for the session"""
        # Get session to find simulator
        session = await self.store_manager.session_store.get_session_from_db(self.session_id, skip_activity_check=force)
        if not session:
            return False, "Session not found"

        # Extract simulator details from metadata
        metadata = session.metadata
        simulator_id = getattr(metadata, 'simulator_id', None)

        if not simulator_id:
            return True, ""

        # Delegate to simulator operations
        success, error = await self.simulator_ops.stop_simulator(force)

        # Update session metadata
        await self.update_session_metadata({
            'simulator_status': 'STOPPED',
            'simulator_id': None,
            'simulator_endpoint': None
        })

        # Publish event that simulator was stopped
        if success:
            await event_bus.publish('simulator_stopped',
                                    session_id=self.session_id,
                                    simulator_id=simulator_id)

        return success, error

    # Also simplify the cleanup_session method
    async def cleanup_session(self):
        """Clean up the session resources"""
        # Get session to find simulator
        session = await self.get_session()
        if session:
            metadata = session.metadata
            simulator_id = getattr(metadata, 'simulator_id', None)
            if simulator_id:
                await self.stop_simulator(force=True)

        logger.info(f"Cleaned up session {self.session_id}")
        return True
