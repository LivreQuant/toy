"""
Background cleanup tasks for singleton session service.
Simplified for a single persistent session.
"""
import logging
import time
import asyncio
from opentelemetry import trace

from source.models.simulator import SimulatorStatus

from source.config import config

from source.utils.event_bus import event_bus
from source.utils.metrics import track_cleanup_operation, track_session_count, track_simulator_count

logger = logging.getLogger('tasks')


class Tasks:
    """Handles background cleanup tasks for session service"""

    def __init__(self, session_manager):
        """
        Initialize with reference to session manager

        Args:
            session_manager: Parent SessionManager instance
        """
        self.manager = session_manager
        self.tracer = trace.get_tracer("session_tasks")

    async def _check_starting_simulators(self):
        """Check if any simulators in STARTING state are now ready"""
        try:
            # In singleton mode, we only care about our session's simulator
            session_id = self.manager.singleton_session_id
            
            # Get session metadata
            metadata = await self.manager.get_session_metadata(session_id)
            
            if not metadata:
                return
                
            simulator_id = metadata.get('simulator_id')
            simulator_status = metadata.get('simulator_status')
            
            # If we have a simulator and it's in STARTING state
            if simulator_id and simulator_status == 'STARTING':
                # Check if it's ready
                is_ready = await self.manager.simulator_manager.check_simulator_ready(simulator_id)
                
                if is_ready:
                    logger.info(f"Simulator {simulator_id} is now RUNNING")
                    
                    # Update session metadata
                    await self.manager.update_session_metadata(session_id, {
                        'simulator_status': 'RUNNING'
                    })
                    
                    # Publish simulator ready event
                    endpoint = metadata.get('simulator_endpoint')
                    await event_bus.publish('simulator_ready',
                                            session_id=session_id,
                                            simulator_id=simulator_id,
                                            endpoint=endpoint)
        except Exception as e:
            logger.error(f"Error checking starting simulators: {e}", exc_info=True)

    async def check_and_handle_orphaned_sessions(self):
        """Check for and handle orphaned sessions (user left without proper cleanup)"""
        try:
            # Get state manager
            state_manager = self.manager.app.get('state_manager')
            if not state_manager:
                logger.warning("State manager not available in session manager")
                return
                
            # If service is active but no WebSocket connections for a certain time
            if state_manager.is_active():
                session_id = state_manager.get_active_session_id()
                if session_id:
                    # Check frontend connections count from session manager
                    active_connection_count = self.manager.frontend_connections
                        
                    # If no active connections for more than 5 minutes, reset
                    connection_time = state_manager.get_active_connection_time()
                    inactive_threshold = 300  # 5 minutes
                        
                    if active_connection_count == 0 and connection_time and (time.time() - connection_time) > inactive_threshold:
                        logger.warning(f"Detected orphaned session {session_id} - no connections for over 5 minutes")
                            
                        # Clean up session resources
                        await self.manager.cleanup_session(session_id)
                            
                        # Reset state
                        await state_manager.reset_to_ready()
                        logger.info("Reset service to ready state after cleaning up orphaned session")
        except Exception as e:
            logger.error(f"Error checking for orphaned sessions: {e}")

    async def run_cleanup_loop(self):
        """Background loop for periodic checks and updates"""
        logger.info("Session maintenance loop starting.")
        while True:
            try:
                logger.info("Running periodic maintenance...")
                
                # Check if simulator in STARTING state has become ready
                await self._check_starting_simulators()
                
                # Check for orphaned sessions
                await self.check_and_handle_orphaned_sessions()
                
                # Update metrics
                if self.manager.singleton_mode:
                    track_session_count(1)  # Always 1 session in singleton mode
                
                    # Track simulator count
                    metadata = await self.manager.get_session_metadata(self.manager.singleton_session_id)
                    has_simulator = bool(metadata and metadata.get('simulator_id'))
                    track_simulator_count(1 if has_simulator else 0)
                
                logger.info("Periodic maintenance finished.")
                
                # Sleep until next cycle
                await asyncio.sleep(60)  # Check every minute
            except asyncio.CancelledError:
                logger.info("Maintenance loop cancelled.")
                break
            except Exception as e:
                logger.error(f"Error in maintenance loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Retry after a minute

    async def cleanup_pod_sessions(self, pod_name):
        """Clean up the singleton session before shutdown"""
        logger.info("Starting cleanup of singleton session resources.")
        
        if self.manager.singleton_mode:
            session_id = self.manager.singleton_session_id
            
            try:
                # Get session metadata
                metadata = await self.manager.get_session_metadata(session_id)
                
                if not metadata:
                    logger.warning(f"No metadata found for session {session_id} during cleanup")
                    return
                
                # Check if there's a simulator to clean up
                simulator_id = metadata.get('simulator_id')
                simulator_status = metadata.get('simulator_status')
                
                if simulator_id and simulator_status != 'STOPPED':
                    logger.info(f"Stopping simulator {simulator_id} for session {session_id} during shutdown")
                    
                    # Stop the simulator
                    try:
                        await self.manager.stop_simulator(session_id, force=True)
                        logger.info(f"Successfully stopped simulator {simulator_id}")
                    except Exception as e:
                        logger.error(f"Error stopping simulator {simulator_id} during shutdown: {e}")
                
                # Update session metadata to mark cleanup
                await self.manager.update_session_metadata(session_id, {
                    'pod_terminating': True,
                    'termination_time': time.time(),
                    'simulator_status': 'STOPPED',
                    'simulator_id': None,
                    'simulator_endpoint': None
                })
                
                logger.info(f"Session {session_id} resources cleaned up during shutdown")
            except Exception as e:
                logger.error(f"Error during session cleanup: {e}", exc_info=True)
                