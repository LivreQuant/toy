"""
Session creation, validation, and management operations.
"""
import logging
import time
import json
from typing import Optional, Tuple
from opentelemetry import trace

from source.models.session import Session, SessionStatus
from source.models.simulator import SimulatorStatus
from source.utils.metrics import track_session_operation, track_session_count, track_session_ended
from source.utils.tracing import optional_trace_span

logger = logging.getLogger('session_operations')


class SessionOperations:
    """Handles core session operations"""

    def __init__(self, session_manager):
        """
        Initialize with reference to the session manager
        
        Args:
            session_manager: Parent SessionManager instance
        """
        self.manager = session_manager
        self.tracer = trace.get_tracer("session_operations")

    async def get_user_from_token(self, token: str) -> Optional[str]:
        """Extract user ID from token via AuthClient"""
        validation = await self.manager.auth_client.validate_token(token)
        if validation.get('valid', False):
            return validation.get('userId')
        return None

    async def create_session(self, user_id: str, device_id: str, token: str, ip_address: Optional[str] = None) -> Tuple[
        Optional[str], bool]:
        """
        Create a new session for a user with device ID, ensuring only one active session per user.

        Args:
            user_id: The user ID (extracted from the token)
            device_id: The device ID from the current connection attempt
            token: Authentication token (used for potential actions like stopping old simulator)
            ip_address: Client IP address

        Returns:
            Tuple of (session_id, is_new) or (None, False) on error
        """
        with optional_trace_span(self.tracer, "create_session") as span:
            span.set_attribute("user_id", user_id)
            span.set_attribute("device_id", device_id)
            span.set_attribute("ip_address", ip_address)

            try:
                # --- Enforce Single Session per User ---
                active_sessions = await self.manager.db_manager.get_active_user_sessions(user_id)
                for old_session in active_sessions:
                    logger.warning(f"User {user_id} has existing active session {old_session.session_id}. Ending it.")
                    span.add_event("Ending existing session", {"old_session_id": old_session.session_id})
                    # Force stop the simulator associated with the old session
                    await self.manager.stop_simulator(old_session.session_id, token=token, force=True)  # Use force=True
                    # Mark the old session as expired in DB
                    await self.manager.db_manager.update_session_status(old_session.session_id,
                                                                        SessionStatus.EXPIRED.value)

                # Create new session in DB
                session_id, is_new = await self.manager.db_manager.create_session(user_id, ip_address)
                span.set_attribute("session_id", session_id)
                span.set_attribute("is_new", is_new)  # Should always be true after cleanup

                if not session_id:
                    logger.error(f"Failed to create session record in DB for user {user_id}")
                    span.set_attribute("error", "DB session creation failed")
                    return None, False

                # Set essential metadata including the validated device_id and current pod
                await self.manager.db_manager.update_session_metadata(session_id, {
                    'pod_name': self.manager.pod_name,
                    'ip_address': ip_address,
                    'device_id': device_id,  # Store the device ID associated with this session
                    'frontend_connections': 0,  # Initialize connection count
                    'reconnect_count': 0
                })

                # Track session creation metric
                track_session_operation("create")

                # Publish session creation event if Redis is available
                if self.manager.redis:
                    try:
                        await self.manager.redis.publish('session_events', json.dumps({
                            'type': 'session_created',
                            'session_id': session_id,
                            'user_id': user_id,
                            'device_id': device_id,
                            'pod_name': self.manager.pod_name,
                            'timestamp': time.time()
                        }))
                    except Exception as e:
                        logger.error(f"Failed to publish session creation event to Redis for {session_id}: {e}")

                # Update active session count metric
                active_session_count = await self.manager.db_manager.get_active_session_count()
                track_session_count(active_session_count, self.manager.pod_name)

                logger.info(f"Successfully created new session {session_id} for user {user_id}, device {device_id}")
                return session_id, is_new  # is_new should be True

            except Exception as e:
                logger.error(f"Error during session creation for user {user_id}: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return None, False

    async def get_session(self, session_id: str) -> Session:
        """
        Get session details as a dictionary.

        Args:
            session_id: The session ID

        Returns:
            Session details dict if found and valid, None otherwise
        """
        with optional_trace_span(self.tracer, "get_session") as span:
            span.set_attribute("session_id", session_id)
            try:
                session = await self.manager.db_manager.get_session_from_db(session_id)  # Fetches Session object

                if not session:
                    span.set_attribute("session_found", False)
                    logger.debug(f"Session {session_id} not found in DB.")
                    return None

                # Check if session is expired (should be handled by get_session query, but double check)
                if session.is_expired():
                    span.set_attribute("session_expired", True)
                    logger.warning(f"get_session retrieved an expired session {session_id}")
                    return None

                span.set_attribute("session_found", True)
                span.set_attribute("user_id", session.user_id)
                # Convert Session object to dictionary for return
                return session

            except Exception as e:
                logger.error(f"Error getting session {session_id}: {e}", exc_info=True)
                span.record_exception(e)
                return None

    async def validate_session(self, session_id: str, token: str, device_id: Optional[str] = None) -> Optional[str]:
        """
        Validate session, token, and optionally device ID. Updates activity on success.

        Args:
            session_id: The session ID
            token: Authentication token
            device_id: Optional device ID to validate against stored metadata

        Returns:
            User ID if valid, None otherwise
        """
        with optional_trace_span(self.tracer, "validate_session") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("has_token", token is not None)
            span.set_attribute("device_id_provided", device_id is not None)

            # 1. Validate token first (less expensive than DB call)
            validation = await self.manager.auth_client.validate_token(token)
            span.set_attribute("token_valid", validation.get('valid', False))

            if not validation.get('valid', False):
                logger.warning(f"Invalid token provided for session validation {session_id}")
                span.set_attribute("validation_error", "Invalid token")
                return None

            user_id = validation.get('userId')
            span.set_attribute("user_id_from_token", user_id)
            if not user_id:
                logger.error(f"Token validation succeeded but no userId returned for session {session_id}")
                span.set_attribute("validation_error", "Missing userId in token")
                return None

            # 2. Get session from database
            session = await self.manager.db_manager.get_session_from_db(session_id)  # Fetches Session object
            span.set_attribute("session_found_in_db", session is not None)

            if not session:
                logger.warning(f"Session {session_id} not found in DB during validation.")
                span.set_attribute("validation_error", "Session not found")
                return None

            # 3. Check if session belongs to the user from the token
            if session.user_id != user_id:
                logger.warning(f"Session {session_id} user mismatch. DB: {session.user_id}, Token: {user_id}")
                span.set_attribute("validation_error", "User ID mismatch")
                return None

            # 4. Check if session is expired (get_session should handle this, but double-check)
            if session.is_expired():
                logger.warning(f"Session {session_id} has expired (checked during validation).")
                span.set_attribute("validation_error", "Session expired")
                return None

            # 5. If device_id provided, validate it matches the one stored in metadata
            if device_id:
                stored_device_id = getattr(session.metadata, 'device_id', None)
                span.set_attribute("stored_device_id", stored_device_id)
                if stored_device_id != device_id:
                    logger.warning(
                        f"Device ID mismatch for session {session_id}. Expected: {stored_device_id}, Got: {device_id}")
                    span.set_attribute("validation_error", "Device ID mismatch")
                    return None  # Strict check: if device ID is provided, it MUST match

            # 6. Validation successful, update session activity
            # Use the dedicated DB method for this
            update_success = await self.manager.db_manager.update_session_activity(session_id)
            if not update_success:
                logger.warning(f"Failed to update session activity for {session_id} after validation.")
                # Decide if this should be a validation failure - perhaps not, log and continue.
                span.set_attribute("activity_update_failed", True)

            span.set_attribute("validation_successful", True)
            logger.debug(f"Session {session_id} validated successfully for user {user_id}.")
            return user_id  # Return user ID on successful validation

    async def update_session_activity(self, session_id: str) -> bool:
        """
        Update the session activity timestamp in the database.

        Args:
            session_id: The session ID

        Returns:
            Success status
        """
        try:
            # Use the dedicated DB method
            success = await self.manager.db_manager.update_session_activity(session_id)
            if not success:
                logger.warning(f"DB update_session_activity returned False for session {session_id}")
            return success
        except Exception as e:
            logger.error(f"Error updating session activity for {session_id}: {e}", exc_info=True)
            return False

    async def end_session(self, session_id: str, token: str) -> Tuple[bool, str]:
        """
        End a session gracefully. Validates token, stops simulator, updates DB.

        Args:
            session_id: The session ID
            token: Authentication token

        Returns:
            Tuple of (success, error_message)
        """
        with optional_trace_span(self.tracer, "end_session") as span:
            span.set_attribute("session_id", session_id)

            # 1. Validate session and token first
            user_id = await self.validate_session(session_id, token)  # Validation updates activity if successful
            span.set_attribute("user_id", user_id)
            span.set_attribute("session_valid", user_id is not None)

            if not user_id:
                error_msg = "Invalid session or token for ending session."
                span.set_attribute("error", error_msg)
                logger.warning(f"Attempt to end session {session_id} failed validation.")
                return False, error_msg

            try:
                # 2. Get current session details (needed for simulator info and lifetime metric)
                session = await self.manager.db_manager.get_session_from_db(session_id)
                if not session:
                    # Should not happen if validation passed, but handle defensively
                    logger.error(f"Session {session_id} passed validation but not found for ending.")
                    span.set_attribute("error", "Session vanished after validation")
                    return False, "Session not found unexpectedly"

                session_created_at = session.created_at
                metadata = session.metadata

                # 3. Stop associated simulator (if any) - Use force=True as we are ending the session
                sim_id = getattr(metadata, 'simulator_id', None)
                sim_status = getattr(metadata, 'simulator_status', SimulatorStatus.NONE)
                span.set_attribute("simulator_id", sim_id)
                span.set_attribute("initial_simulator_status", sim_status.value if sim_status else 'NONE')

                if sim_id and sim_status != SimulatorStatus.STOPPED:
                    logger.info(f"Stopping simulator {sim_id} as part of ending session {session_id}.")
                    # Use force=True because the session is ending regardless
                    sim_stopped, sim_stop_error = await self.manager.stop_simulator(session_id, token=token, force=True)
                    if not sim_stopped:
                        # Log error but continue ending the session
                        logger.error(f"Failed to stop simulator {sim_id} during session end: {sim_stop_error}")
                        span.set_attribute("simulator_stop_error", sim_stop_error)
                    else:
                        logger.info(f"Simulator {sim_id} stopped successfully during session end.")
                        span.set_attribute("simulator_stopped", True)

                # 4. End session in database (mark as EXPIRED or delete)
                # Assuming db_manager.end_session marks as EXPIRED or deletes
                # Let's assume it marks as EXPIRED for potential auditing
                success = await self.manager.db_manager.update_session_status(session_id, SessionStatus.EXPIRED.value)

                if not success:
                    logger.error(f"Failed to mark session {session_id} as EXPIRED in DB.")
                    span.set_attribute("error", "Failed to update session status in DB")
                    # Don't return failure here if simulator stop worked, maybe DB issue is transient
                    # return False, "Failed to update session status in database"

                # 5. Calculate session lifetime and record metric
                lifetime = time.time() - session_created_at
                track_session_ended(lifetime, "completed")
                track_session_operation("end")
                span.set_attribute("session_lifetime_seconds", lifetime)

                # 6. Update active session count metric
                active_session_count = await self.manager.db_manager.get_active_session_count()
                track_session_count(active_session_count, self.manager.pod_name)

                # 7. Publish session end event if Redis is available
                if self.manager.redis:
                    try:
                        await self.manager.redis.publish('session_events', json.dumps({
                            'type': 'session_ended',
                            'session_id': session_id,
                            'user_id': user_id,
                            'pod_name': self.manager.pod_name,
                            'timestamp': time.time()
                        }))
                    except Exception as e:
                        logger.error(f"Failed to publish session end event to Redis for {session_id}: {e}")

                logger.info(f"Session {session_id} ended successfully for user {user_id}.")
                return True, ""

            except Exception as e:
                logger.error(f"Unexpected error ending session {session_id}: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return False, f"Server error ending session: {str(e)}"
