"""
Simulator management operations for the session service.
Handles creating, stopping, and monitoring exchange simulators.
"""
import logging
import time
import json
from typing import List, Optional, Tuple
from opentelemetry import trace

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

    async def start_simulator(self, session_id: str, token: str, symbols: List[str] = None) -> Tuple[
        Optional[str], Optional[str], str]:
        """
        Start a simulator for a session, ensuring only one runs per session.

        Args:
            session_id: The session ID
            token: Authentication token
            symbols: List of symbols to track (optional, uses default if None)

        Returns:
            Tuple of (simulator_id, endpoint, error_message) - IDs are for internal use, not frontend.
            Returns (None, None, error_message) on failure.
            Returns existing simulator details if already running.
        """
        with optional_trace_span(self.tracer, "start_simulator") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("has_symbols", symbols is not None)

            # 1. Validate session
            user_id = await self.manager.session_ops.validate_session(session_id, token)  # Validation updates activity
            span.set_attribute("user_id", user_id)
            span.set_attribute("session_valid", user_id is not None)

            if not user_id:
                error_msg = "Invalid session or token for starting simulator."
                span.set_attribute("error", error_msg)
                return None, None, error_msg

            try:
                # 2. Get current session details
                session = await self.manager.db_manager.get_session_from_db(session_id)
                if not session:  # Should not happen
                    logger.error(f"Session {session_id} passed validation but not found for starting simulator.")
                    span.set_attribute("error", "Session vanished after validation")
                    return None, None, "Session not found unexpectedly"

                metadata = session.metadata
                sim_id = getattr(metadata, 'simulator_id', None)
                sim_endpoint = getattr(metadata, 'simulator_endpoint', None)
                sim_status = getattr(metadata, 'simulator_status', SimulatorStatus.NONE)
                span.set_attribute("existing_simulator_id", sim_id)
                span.set_attribute("existing_simulator_status", sim_status.value if sim_status else 'NONE')

                # 3. Check if there's already an active simulator for this session
                if sim_id and sim_status != SimulatorStatus.STOPPED and sim_status != SimulatorStatus.ERROR:
                    # Verify simulator is actually running via K8s check or gRPC status?
                    # For now, trust the DB status if it's STARTING or RUNNING
                    if sim_status in [SimulatorStatus.STARTING, SimulatorStatus.RUNNING]:
                        logger.info(f"Simulator {sim_id} already active for session {session_id}. Returning existing.")
                        span.add_event("Returning existing active simulator")
                        # Return existing details (for internal use)
                        return sim_id, sim_endpoint, ""
                    # If status is CREATING or STOPPING, maybe wait or return error?
                    elif sim_status in [SimulatorStatus.CREATING, SimulatorStatus.STOPPING]:
                        error_msg = f"Simulator action already in progress ({sim_status.value}). Please wait."
                        span.set_attribute("error", error_msg)
                        return None, None, error_msg

                # 4. Create new simulator via SimulatorManager
                logger.info(f"Requesting new simulator creation for session {session_id}")
                # SimulatorManager handles checking user limits and DB/K8s creation
                simulator_obj, error = await self.manager.simulator_manager.create_simulator(
                    session_id,
                    user_id,
                    symbols  # Pass symbols if provided
                    # initial_cash can be added if needed
                )

                span.set_attribute("simulator_creation_requested", True)

                if not simulator_obj:
                    logger.error(f"Failed to create simulator for session {session_id}: {error}")
                    span.set_attribute("error", f"Simulator creation failed: {error}")
                    # Metric tracked within simulator_manager
                    return None, None, error

                # Simulator created successfully by manager (DB updated, K8s started)
                new_sim_id = simulator_obj.simulator_id
                new_endpoint = simulator_obj.endpoint
                new_status = simulator_obj.status  # Should be STARTING or RUNNING
                span.set_attribute("new_simulator_id", new_sim_id)
                span.set_attribute("new_simulator_endpoint", new_endpoint)
                span.set_attribute("new_simulator_status", new_status.value)

                # 5. Update session metadata with the new simulator details
                update_success = await self.manager.db_manager.update_session_metadata(session_id, {
                    'simulator_id': new_sim_id,
                    'simulator_endpoint': new_endpoint,
                    'simulator_status': new_status.value  # Store enum value
                })
                if not update_success:
                    logger.warning(f"Failed to update session metadata after starting simulator {new_sim_id}")
                    span.set_attribute("metadata_update_failed", True)
                    # Continue, but log the issue

                # 6. Publish simulator started event if Redis is available
                if self.manager.db_manager.redis:
                    try:
                        await self.manager.db_manager.redis.publish('session_events', json.dumps({
                            'type': 'simulator_started',
                            'session_id': session_id,
                            'simulator_id': new_sim_id,
                            'pod_name': self.manager.pod_name,
                            'timestamp': time.time()
                        }))
                    except Exception as e:
                        logger.error(f"Failed to publish simulator start event to Redis for {session_id}: {e}")

                logger.info(f"Successfully started simulator {new_sim_id} for session {session_id}")
                # Return new details (for internal use)
                return new_sim_id, new_endpoint, ""

            except Exception as e:
                logger.error(f"Unexpected error starting simulator for session {session_id}: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                # Attempt to mark simulator as ERROR in DB if we know its ID? Difficult state.
                return None, None, f"Server error starting simulator: {str(e)}"

    # Continuing with simulator_operations.py

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
                        await self.manager.db_manager.redis.publish('session_events', json.dumps({
                            'type': 'simulator_stopped',
                            'session_id': session_id,
                            'simulator_id': simulator_id,  # Include ID in event
                            'user_id': user_id,  # Include user if available
                            'pod_name': self.manager.pod_name,
                            'timestamp': time.time(),
                            'forced': force
                        }))
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
