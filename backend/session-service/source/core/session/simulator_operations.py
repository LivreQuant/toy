"""
Simulator management operations for the session service.
Handles creating, stopping, and monitoring exchange simulators.
"""
import logging
import asyncio
import random
from typing import Optional, Tuple
from opentelemetry import trace

from source.config import config
from source.models.simulator import SimulatorStatus
from source.utils.tracing import optional_trace_span

logger = logging.getLogger('simulator_operations')


class SimulatorOperations:
    """Handles simulator-related operations"""

    def __init__(self, session_manager):
        """
        Initialize with reference to session manager

        Args:
            session_manager: Parent SessionManager instance
        """
        self.manager = session_manager
        self.tracer = trace.get_tracer("simulator_operations")

    async def start_simulator(self, session_id: str, token: str) -> Tuple[Optional[str], Optional[str], str]:
        """
        Start a simulator for a session, ensuring only one runs per session.

        Args:
            session_id: The session ID
            token: Authentication token

        Returns:
            Tuple of (simulator_id, endpoint, error_message)
        """
        with optional_trace_span(self.tracer, "start_simulator") as span:
            span.set_attribute("session_id", session_id)

            logger.info(f"session_simulator_operation - start_simulator - session validation: {session_id}")

            # 1. Validate session
            user_id = await self.manager.session_ops.validate_session(session_id, token)
            span.set_attribute("user_id", user_id)
            span.set_attribute("session_valid", user_id is not None)

            if not user_id:
                error_msg = "Invalid session or token for starting simulator."
                span.set_attribute("error", error_msg)
                return None, None, error_msg

            try:
                # 2. Get current session details
                session = await self.manager.db_manager.get_session_from_db(session_id)
                if not session:
                    logger.error(f"Session {session_id} passed validation but not found.")
                    span.set_attribute("error", "Session vanished after validation")
                    return None, None, "Session not found unexpectedly"

                # 3. Check existing simulators for user
                #active_simulators = await self.manager.db_manager.get_active_user_simulators(user_id)
                
                #if len(active_simulators) >= config.simulator.max_per_user:
                    # Optional: Automatically stop the oldest simulator
                    #oldest_simulator = min(active_simulators, key=lambda s: s.created_at)
                    #stop_result, stop_error = await self.stop_simulator(
                    #    oldest_simulator.session_id, 
                    #    token, 
                    #    force=False
                    #)
                    #if not stop_result:
                    #    return None, None, f"Cannot start simulator. {stop_error}"

                # 4. Check if a simulator already exists for this session
                metadata = session.metadata
                sim_id = getattr(metadata, 'simulator_id', None)
                sim_endpoint = getattr(metadata, 'simulator_endpoint', None)
                sim_status = getattr(metadata, 'simulator_status', SimulatorStatus.NONE)

                # If simulator exists and is not stopped/errored, return its details
                if (sim_id and sim_status not in 
                    [SimulatorStatus.STOPPED, SimulatorStatus.ERROR]):
                    logger.info(f"Returning existing active simulator {sim_id} for session {session_id}")
                    return sim_id, sim_endpoint, ""

                # 5. Create new simulator
                logger.info(f"Creating new simulator for session {session_id}")
                simulator_obj, error = await self.manager.simulator_manager.create_simulator(
                    session_id, 
                    user_id
                )

                if not simulator_obj:
                    logger.error(f"Simulator creation failed: {error}")
                    return None, None, error

                # 6. Update session metadata
                new_sim_id = simulator_obj.simulator_id
                new_endpoint = simulator_obj.endpoint
                new_status = simulator_obj.status

                await self.manager.db_manager.update_session_metadata(session_id, {
                    'simulator_id': new_sim_id,
                    'simulator_endpoint': new_endpoint,
                    'simulator_status': new_status.value
                })

                # 7. Publish event
                if self.manager.db_manager.redis:
                    try:
                        await self.manager.db_manager.redis.publish_session_event('simulator_started', {
                            'session_id': session_id,
                            'simulator_id': new_sim_id,
                            'user_id': user_id
                        })
                    except Exception as e:
                        logger.error(f"Failed to publish simulator start event: {e}")

                # 8. Start exchange stream
                try:
                    stream_task = await self.start_exchange_stream(session_id, token)
                    if stream_task:
                        # Optional: Register stream task if you're using StreamManager
                        self.manager.stream_manager.register_stream(session_id, stream_task)
                except Exception as stream_error:
                    logger.error(f"Failed to start exchange stream: {stream_error}")

                logger.info(f"Successfully started simulator {new_sim_id} for session {session_id}")
                return new_sim_id, new_endpoint, ""

            except Exception as e:
                logger.error(f"Unexpected error starting simulator: {e}", exc_info=True)
                return None, None, f"Server error: {str(e)}"
            
    async def stop_simulator(self, session_id: str, token: Optional[str] = None, force: bool = False) -> Tuple[
        bool, str]:
        """
        Stop the simulator for a session.

        Args:
            session_id: The session ID
            token: Authentication token (required if force=False)
            force: Force stop without token validation (used for cleanup)

        Returns:
            Tuple of (success, error_message)
        """
        with optional_trace_span(self.tracer, "stop_simulator") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("force_stop", force)

            user_id = None
            if not force:
                if not token:
                    error_msg = "Missing authentication token for stopping simulator."
                    span.set_attribute("error", error_msg)
                    return False, error_msg
                
                logger.info(f"session_simulator_operation - stop_simulator - session validation: {session_id}")

                # Validate session if not forcing
                user_id = await self.manager.session_ops.validate_session(session_id,
                                                                          token)  # Validation updates activity
                span.set_attribute("user_id", user_id)
                span.set_attribute("session_valid", user_id is not None)
                if not user_id:
                    error_msg = "Invalid session or token for stopping simulator."
                    span.set_attribute("error", error_msg)
                    return False, error_msg
            # If forcing, we proceed without user_id validation here

            try:
                # 1. Get session details to find the simulator ID
                session = await self.manager.db_manager.get_session_from_db(session_id)
                if not session:
                    # If forcing, session might already be gone, log and return success
                    if force:
                        logger.warning(
                            f"Session {session_id} not found during forced simulator stop (might be already cleaned up).")
                        return True, ""
                    else:
                        error_msg = "Session not found for stopping simulator."
                        span.set_attribute("error", error_msg)
                        return False, error_msg

                metadata = session.metadata
                simulator_id = getattr(metadata, 'simulator_id', None)
                sim_status = getattr(metadata, 'simulator_status', SimulatorStatus.NONE)
                span.set_attribute("simulator_id", simulator_id)
                span.set_attribute("initial_simulator_status", sim_status.value if sim_status else 'NONE')

                # 2. Check if there's an active simulator to stop
                if not simulator_id:
                    logger.info(f"No active simulator found for session {session_id} to stop.")
                    span.add_event("No simulator found to stop")
                    # If no simulator exists, consider it a success (idempotency)
                    return True, ""
                if sim_status == SimulatorStatus.STOPPED:
                    logger.info(f"Simulator {simulator_id} for session {session_id} is already stopped.")
                    span.add_event("Simulator already stopped")
                    return True, ""  # Idempotent

                # 3. Stop simulator via SimulatorManager
                logger.info(f"Requesting simulator stop for {simulator_id} (Session: {session_id}, Force: {force})")
                # SimulatorManager handles DB updates and K8s deletion
                success, error = await self.manager.simulator_manager.stop_simulator(simulator_id)
                span.set_attribute("simulator_stop_success", success)

                if not success:
                    logger.error(f"Failed to stop simulator {simulator_id} via manager: {error}")
                    span.set_attribute("error", f"Simulator stop failed: {error}")
                    # Even if manager fails, update metadata if possible
                    # Fall through to update metadata

                # 4. Update session metadata to reflect simulator stopped status
                # Ensure simulator_id is cleared even if stop failed to prevent reuse
                update_success = await self.manager.db_manager.update_session_metadata(session_id, {
                    'simulator_status': SimulatorStatus.STOPPED.value,
                    'simulator_id': None,  # Clear simulator ID
                    'simulator_endpoint': None  # Clear endpoint
                })
                if not update_success:
                    logger.warning(f"Failed to update session metadata after stopping simulator {simulator_id}")
                    span.set_attribute("metadata_update_failed", True)
                    # Don't fail the call if simulator stop itself succeeded

                # 5. Publish simulator stopped event if Redis is available
                if self.manager.db_manager.redis:
                    # Get user_id if forcing and session was found
                    if force and not user_id:
                        user_id = session.user_id

                    try:
                        await self.manager.db_manager.redis.publish_session_event('simulator_stopped', {
                            'session_id': session_id,
                            'simulator_id': simulator_id,  # Include ID in event
                            'user_id': user_id,  # Include user if available
                            'forced': force
                        })
                    except Exception as e:
                        logger.error(f"Failed to publish simulator stop event to Redis for {session_id}: {e}")

                logger.info(
                    f"Simulator stop process completed for {simulator_id} (Session: {session_id}). Success: {success}")
                # Return overall success based on the simulator manager's result
                return success, error if not success else ""

            except Exception as e:
                logger.error(f"Unexpected error stopping simulator for session {session_id}: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return False, f"Server error stopping simulator: {str(e)}"

    async def start_exchange_stream(self, session_id: str, token: str) -> Optional[asyncio.Task]:
        """
        Start an exchange data stream for a given session
        """
        with optional_trace_span(self.tracer, "start_exchange_stream") as span:
            logger.info(f"Attempting to start exchange stream for session {session_id}")
            
            max_attempts = 5
            base_delay = 1  # Initial delay in seconds
            max_delay = 30  # Maximum delay between attempts

            for attempt in range(max_attempts):
                try:
                    # Get session details
                    session = await self.manager.db_manager.get_session_from_db(session_id)
                    
                    if not session:
                        logger.error(f"No session found for {session_id}")
                        return None

                    # Extract simulator endpoint
                    simulator_endpoint = getattr(session.metadata, 'simulator_endpoint', None)
                    
                    if not simulator_endpoint:
                        logger.error("No simulator endpoint found")
                        return None

                    # Exponential backoff calculation
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                    
                    # First, send a heartbeat to verify the simulator is ready
                    logger.info(f"Attempting heartbeat (Attempt {attempt + 1}): Delay {delay:.2f}s")
                    await asyncio.sleep(delay)  # Backoff before retry

                    heartbeat_result = await self.exchange_client.send_heartbeat(
                        simulator_endpoint, 
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
                                        simulator_endpoint, 
                                        session_id, 
                                        f"stream-{session_id}"
                                    ):
                                        # Reset stream attempts on successful connection
                                        stream_attempts = 0
                                        
                                        # Broadcast to all WebSocket clients for this session
                                        await self.websocket_manager.broadcast_to_session(session_id, {
                                            'type': 'exchange_data',
                                            'data': data
                                        })
                                
                                except Exception as stream_error:
                                    stream_attempts += 1
                                    stream_delay = min(base_delay * (2 ** stream_attempts) + random.uniform(0, 1), max_delay)
                                    
                                    logger.warning(
                                        f"Stream connection attempt {stream_attempts} failed. "
                                        f"Error: {stream_error}. "
                                        f"Waiting {stream_delay:.2f}s before retry"
                                    )
                                    
                                    # Update simulator status for persistent errors
                                    if stream_attempts >= max_stream_attempts:
                                        logger.error(f"Exceeded max stream connection attempts for session {session_id}")
                                        await self.manager.db_manager.update_session_metadata(session_id, {
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
                        await self.manager.db_manager.update_session_metadata(session_id, {
                            'simulator_status': 'ERROR'
                        })
                        return None

                except Exception as e:
                    logger.error(f"Error in exchange stream initialization (Attempt {attempt + 1}): {e}")
                    
                    # On final attempt, mark as error
                    if attempt == max_attempts - 1:
                        await self.manager.db_manager.update_session_metadata(session_id, {
                            'simulator_status': 'ERROR'
                        })
                        return None

            # If all attempts fail
            return None