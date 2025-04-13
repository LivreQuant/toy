"""
Session manager for handling a single user session.
Coordinates the core components for session management.
"""
import logging
import asyncio
from typing import Optional, Dict, Any

from opentelemetry import trace

from source.config import config

from source.utils.event_bus import event_bus

from source.db.manager import StoreManager

from source.clients.exchange import ExchangeClient

from source.core.stream.manager import StreamManager
from source.core.simulator.manager import SimulatorManager

from source.core.session.simulator_operations import SimulatorOperations
from source.core.session.connection import Connection
from source.core.session.tasks import Tasks


logger = logging.getLogger('session_manager')


class SessionManager:
    """Manager for a single user session - coordinates all session-related operations"""

    def __init__(
            self,
            store_manager: StoreManager,
            exchange_client: ExchangeClient,
            stream_manager: StreamManager,
            simulator_manager: SimulatorManager,
            singleton_mode: bool = False,
            singleton_session_id: str = None
    ):
        """
        Initialize session manager and its component modules

        Args:
            store_manager: PostgreSQL store for session persistence
            exchange_client: Exchange client for simulator communication
            simulator_manager: Manager for simulator operations
            stream_manager: Stream manager for managing background streams
            singleton_mode: Whether to operate in single-user mode
            singleton_session_id: The predefined session ID to use in singleton mode
        """
        self.store_manager = store_manager
        self.exchange_client = exchange_client
        self.stream_manager = stream_manager
        self.simulator_manager = simulator_manager
        
        # Singleton mode settings
        self.singleton_mode = singleton_mode
        self.singleton_session_id = singleton_session_id

        # Initialize component modules
        self.simulator_ops = SimulatorOperations(self)
        self.connection = Connection(self)
        self.tasks = Tasks(self)

        # Background tasks
        self.cleanup_task = None
        self.heartbeat_task = None

        # Connection tracking
        self.frontend_connections = 0

        # Create tracer
        self.tracer = trace.get_tracer("session_manager")

        # Subscribe to events
        event_bus.subscribe('stream_error', self.handle_stream_error)
        event_bus.subscribe('ws_connection_established', self.handle_connection_established)
        event_bus.subscribe('ws_connection_closed', self.handle_connection_closed)

        logger.info(f"Session manager initialized in {'singleton' if singleton_mode else 'multi-user'} mode")
        if singleton_mode:
            logger.info(f"Singleton session ID: {singleton_session_id}")

    # ----- Connection tracking methods -----
    
    async def handle_connection_established(self, session_id, client_id, user_id):
        """Handle new WebSocket connection event"""
        self.frontend_connections += 1
        logger.info(f"New connection established (total: {self.frontend_connections})")
        
        # Update session metadata
        await self.update_session_metadata(session_id, {
            'frontend_connections': self.frontend_connections,
            'last_ws_connection': asyncio.get_event_loop().time()
        })
        
        # Update session activity
        await self.update_session_activity(session_id)

    async def handle_connection_closed(self, session_id, client_id, session_empty):
        """Handle WebSocket connection closed event"""
        self.frontend_connections = max(0, self.frontend_connections - 1)
        logger.info(f"Connection closed (remaining: {self.frontend_connections})")
        
        # Update session metadata
        await self.update_session_metadata(session_id, {
            'frontend_connections': self.frontend_connections,
            'last_ws_disconnection': asyncio.get_event_loop().time()
        })
    
    # ----- Public API methods -----

    async def get_session_id(self, user_id=None, device_id=None):
        """
        In singleton mode, always return the singleton session ID.
        In multi-user mode, would return the session ID for the given user and device.
        """
        if self.singleton_mode:
            return self.singleton_session_id
        
        # Fallback to original behavior for multi-user mode
        session_id, _ = await self.create_session(user_id, device_id)
        return session_id

    async def create_session(self, user_id, device_id, ip_address=None):
        """
        In singleton mode, just return the singleton session.
        In multi-user mode, create a new session or return existing one.
        """
        if self.singleton_mode:
            # In singleton mode, we just return the predefined session
            return self.singleton_session_id, False
            
        # Original multi-user implementation would go here
        session_id, is_new = await self.store_manager.session_store.create_session(user_id, ip_address)
        
        if session_id and is_new:
            # Update metadata with device ID
            await self.update_session_metadata(session_id, {
                'device_id': device_id,
                'pod_name': config.kubernetes.pod_name
            })
            
            # Publish event that new session was created
            await event_bus.publish('session_created',
                                    session_id=session_id,
                                    user_id=user_id,
                                    device_id=device_id)
        return session_id, is_new

    async def get_session(self, session_id=None):
        """
        Get session by ID. In singleton mode, always get the singleton session.
        """
        if self.singleton_mode:
            session_id = self.singleton_session_id
            
        return await self.store_manager.session_store.get_session_from_db(session_id)

    async def get_session_metadata(self, session_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Get session metadata as a dictionary.
        In singleton mode, always get the singleton session metadata.
        """
        if self.singleton_mode:
            session_id = self.singleton_session_id
            
        session = await self.get_session(session_id)
        if not session or not hasattr(session, 'metadata'):
            return None

        # Convert the SessionMetadata object to a dictionary
        try:
            return session.metadata.dict()
        except Exception as e:
            logger.error(f"Error converting session metadata to dict for {session_id}: {e}")
            return {}

    async def validate_session(self, session_id, user_id, device_id=None):
        """
        Validate session ownership.
        In singleton mode, always validate successfully.
        """
        if self.singleton_mode:
            # In singleton mode, all session validation passes
            return user_id
            
        # Original validation would go here
        session = await self.get_session(session_id)
        if not session:
            return None
            
        # Simple validation - just check user ID
        if session.user_id != user_id:
            return None
            
        return user_id

    async def update_session_activity(self, session_id=None):
        """
        Update session last activity time.
        In singleton mode, always use the singleton session.
        """
        if self.singleton_mode:
            session_id = self.singleton_session_id
            
        success = await self.store_manager.session_store.update_session_activity(session_id)
        if success:
            # Publish event that session activity was updated
            await event_bus.publish('session_activity_updated', session_id=session_id)
        return success

    async def update_session_metadata(self, session_id, metadata_updates):
        """
        Update session metadata.
        In singleton mode, always use the singleton session.
        """
        if self.singleton_mode and session_id != self.singleton_session_id:
            session_id = self.singleton_session_id
            
        success = await self.store_manager.session_store.update_session_metadata(session_id, metadata_updates)
        if success:
            # Publish event that metadata was updated
            await event_bus.publish('session_metadata_updated',
                                    session_id=session_id,
                                    updates=metadata_updates)
        return success

    async def end_session(self, session_id=None, user_id=None):
        """
        End a session and clean up resources.
        In singleton mode, this is a no-op as the singleton session persists.
        """
        if self.singleton_mode:
            # In singleton mode, we don't actually end the session
            logger.warning("Attempted to end singleton session - ignoring")
            return True, ""
            
        # Original end_session code would go here
        # For now, just return success
        return True, ""

    # ----- Simulator operations -----

    async def start_simulator(self, session_id=None, user_id=None):
        """
        Start a simulator for a session.
        In singleton mode, always use the singleton session.
        """
        if self.singleton_mode:
            session_id = self.singleton_session_id
            
        # Delegate to simulator operations
        simulator, error = await self.simulator_ops.create_simulator(session_id, user_id or "default-user")

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
        """Stream simulator data - unchanged"""
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

    async def stop_simulator(self, session_id=None, force=False):
        """
        Stop a simulator for a session.
        In singleton mode, always use the singleton session.
        """
        if self.singleton_mode:
            session_id = self.singleton_session_id
            
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
        """Handle stream error events - unchanged"""
        # Update session metadata to reflect error state if this is a terminal error
        if attempt is not None and max_attempts is not None and attempt >= max_attempts:
            await self.update_session_metadata(session_id, {
                'simulator_status': 'ERROR',
                'simulator_error': error
            })

    # ----- Background tasks -----

    async def start_session_tasks(self):
        """Start background cleanup task and simulator heartbeat task - unchanged"""
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self.tasks.run_cleanup_loop())
            logger.info("Started session cleanup task")

        if self.heartbeat_task is None or self.heartbeat_task.done():
            self.heartbeat_task = asyncio.create_task(self.simulator_ops.run_simulator_heartbeat_loop())
            logger.info("Started simulator heartbeat task")

    async def stop_cleanup_task(self):
        """Stop background cleanup task and heartbeat task - unchanged"""
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

    async def cleanup_session(self, session_id=None):
        """
        Clean up a specific session.
        In singleton mode, always use the singleton session.
        """
        if self.singleton_mode:
            session_id = self.singleton_session_id
            
        # Clean up any simulators associated with this session
        session = await self.get_session(session_id)
        if session:
            metadata = session.metadata
            simulator_id = getattr(metadata, 'simulator_id', None)
            if simulator_id:
                await self.stop_simulator(session_id, force=True)
                
        logger.info(f"Cleaned up session {session_id}")
        return True
    