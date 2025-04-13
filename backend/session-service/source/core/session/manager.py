"""
Session manager for handling a single user session.
Simplified for dedicated single-user service.
"""
import logging
import asyncio
from typing import Optional, Dict, Any, Callable

from opentelemetry import trace

from source.db.manager import StoreManager

from source.clients.exchange import ExchangeClient

from source.core.stream.manager import StreamManager
from source.core.simulator.manager import SimulatorManager

from source.core.session.connection import Connection

logger = logging.getLogger('session_manager')


class SessionManager:
    """Manager for a single user session - core of the session service"""

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

        # Track if we have a simulator
        self.simulator_active = False

        # Callbacks for exchange data
        self.exchange_data_callbacks = set()

        # Initialize connection component
        self.connection = Connection(self)

        # Create tracer
        self.tracer = trace.get_tracer("session_manager")

        # Set up data callback to simulator manager
        self.simulator_manager.set_data_callback(self._handle_exchange_data)

        logger.info(f"Session manager initialized with session ID: {session_id}")

    # ----- Callback management -----

    def register_exchange_data_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        Register a callback to receive exchange data

        Args:
            callback: Function that accepts exchange data dictionary
        """
        self.exchange_data_callbacks.add(callback)
        logger.debug(f"Registered exchange data callback, total: {len(self.exchange_data_callbacks)}")

    def unregister_exchange_data_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        Unregister a previously registered callback

        Args:
            callback: The callback function to remove
        """
        if callback in self.exchange_data_callbacks:
            self.exchange_data_callbacks.remove(callback)
            logger.debug(f"Unregistered exchange data callback, remaining: {len(self.exchange_data_callbacks)}")

    def _handle_exchange_data(self, data: Dict[str, Any]):
        """
        Handle incoming exchange data by forwarding to all registered callbacks

        Args:
            data: Exchange data dictionary
        """
        for callback in list(self.exchange_data_callbacks):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Error in exchange data callback: {e}")
                # Consider removing problematic callbacks

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
        return await self.store_manager.session_store.update_session_activity(self.session_id)

    async def update_session_metadata(self, metadata_updates):
        """Update session metadata"""
        return await self.store_manager.session_store.update_session_metadata(self.session_id, metadata_updates)

    # ----- Simulator operations -----

    async def start_simulator(self, user_id=None):
        """Start a simulator for the session"""
        # Use user ID from the session if not specified
        if not user_id:
            session = await self.get_session()
            user_id = session.user_id if session else "default-user"

        # Start the simulator
        simulator, error = await self.simulator_manager.create_simulator(self.session_id, user_id)

        if simulator and not error:
            # Update session metadata with simulator info
            await self.update_session_metadata({
                'simulator_id': simulator.simulator_id,
                'simulator_status': simulator.status.value,
                'simulator_endpoint': simulator.endpoint
            })

            # Set flag for active simulator
            self.simulator_active = True

            # Start exchange stream if simulator created successfully
            try:
                # Create the exchange data stream task
                stream_task = asyncio.create_task(
                    self._stream_simulator_data(simulator.endpoint, simulator.simulator_id)
                )
                stream_task.set_name(f"stream-{simulator.simulator_id}")

                # Register with stream manager
                if stream_task and self.stream_manager:
                    self.stream_manager.register_stream(self.session_id, stream_task)

            except Exception as e:
                logger.error(f"Failed to start exchange stream: {e}", exc_info=True)

            return simulator.simulator_id, simulator.endpoint, ""

        return None, None, error

    async def _stream_simulator_data(self, endpoint: str, simulator_id: str):
        """Stream simulator data - data is handled via callback now"""
        try:
            # Stream data - handling will occur via callbacks
            async for _ in self.simulator_manager.stream_exchange_data(
                endpoint,
                self.session_id,
                f"stream-{self.session_id}"
            ):
                # The simulator manager will call our _handle_exchange_data method
                # for each data item. We just need to keep the stream running.
                pass

        except Exception as e:
            logger.error(f"Error in simulator data streaming: {e}")
            self.simulator_active = False

            # Update session metadata to reflect error
            await self.update_session_metadata({
                'simulator_status': 'ERROR',
            })

    async def stop_simulator(self, force=False):
        """Stop the current simulator"""
        # First check if there's a simulator to stop
        metadata = await self.get_session_metadata()
        if not metadata or not metadata.get('simulator_id'):
            return True, "No simulator to stop"

        simulator_id = metadata.get('simulator_id')

        # Stop via the simulator manager
        success, error = await self.simulator_manager.stop_simulator(simulator_id, force)

        # Update session metadata
        await self.update_session_metadata({
            'simulator_status': 'STOPPED',
            'simulator_id': None,
            'simulator_endpoint': None
        })

        # Update state tracking
        self.simulator_active = False

        # Stop the stream if running
        if self.stream_manager:
            await self.stream_manager.stop_stream(self.session_id)

        return success, error

    async def cleanup_session(self):
        """Clean up the session resources - important for graceful shutdown"""
        # Stop simulator if active
        if self.simulator_active:
            await self.stop_simulator(force=True)

        # Make sure all streams are stopped
        if self.stream_manager:
            await self.stream_manager.stop_stream(self.session_id)

        logger.info(f"Cleaned up session {self.session_id}")
        return True
    