"""
Session manager for handling user sessions.
Manages user sessions, authentication, and coordinates with simulator manager.
"""
import logging
import time
import asyncio
import json
from typing import Dict, Any, Optional, Tuple, List
from opentelemetry import trace

# Assuming Session, SessionStatus, SimulatorStatus are correctly defined in models
from source.models.session import Session, SessionStatus, SessionMetadata
from source.models.simulator import SimulatorStatus
from source.db.session_store import DatabaseManager
from source.api.clients.auth_client import AuthClient
from source.api.clients.exchange_client import ExchangeClient
from source.core.simulator_manager import SimulatorManager
from source.config import config

from source.utils.metrics import (
    track_session_count, track_session_operation, track_session_ended,
    track_simulator_count, track_simulator_operation, track_connection_quality,
    track_cleanup_operation
)
from source.utils.tracing import optional_trace_span

logger = logging.getLogger('session_manager')

class SessionManager:
    """Manager for user sessions"""

    def __init__(
        self,
        db_manager: DatabaseManager,
        auth_client: AuthClient,
        exchange_client: ExchangeClient,
        redis_client = None,
        websocket_manager = None # Added to handle notifications
    ):
        """
        Initialize session manager

        Args:
            db_manager: Database manager for session persistence
            auth_client: Authentication client for token validation
            exchange_client: Exchange client for simulator communication
            redis_client: Optional Redis client for pub/sub and caching
            websocket_manager: WebSocket manager instance (optional but needed for notifications)
        """
        self.db_manager = db_manager
        self.auth_client = auth_client
        self.exchange_client = exchange_client
        self.redis = redis_client
        self.websocket_manager = websocket_manager # Store websocket manager
        self.pod_name = config.kubernetes.pod_name

        # Create simulator manager
        self.simulator_manager = SimulatorManager(db_manager, exchange_client)

        # Background tasks
        self.cleanup_task = None
        self.heartbeat_task = None # Initialize heartbeat_task attribute

        # Create tracer
        self.tracer = trace.get_tracer("session_manager")

    async def get_combined_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get combined status information for a session
        
        Args:
            session_id: The session ID
            
        Returns:
            Dict with status information
        """
        with optional_trace_span(self.tracer, "get_combined_status") as span:
            span.set_attribute("session_id", session_id)
            
            try:
                # Get session
                session = await self.get_session(session_id)
                if not session:
                    return {
                        'sessionStatus': SessionStatus.ERROR.value,
                        'simulatorStatus': SimulatorStatus.NONE.value,
                        'connectionQuality': ConnectionQuality.POOR.value
                    }
                
                # Extract metadata
                metadata = session.get('metadata', {})
                
                # Get simulator status
                simulator_id = getattr(metadata, 'simulator_id', None)
                simulator_status = getattr(metadata, 'simulator_status', SimulatorStatus.NONE.value)
                
                # Get connection quality
                connection_quality = getattr(metadata, 'connection_quality', ConnectionQuality.GOOD.value)
                
                # Return combined status
                return {
                    'sessionStatus': session.get('status', SessionStatus.ACTIVE.value),
                    'simulatorStatus': simulator_status,
                    'connectionQuality': connection_quality
                }
            except Exception as e:
                logger.error(f"Error getting combined status: {e}", exc_info=True)
                span.record_exception(e)
                return {
                    'sessionStatus': SessionStatus.ERROR.value,
                    'simulatorStatus': SimulatorStatus.ERROR.value,
                    'connectionQuality': ConnectionQuality.POOR.value
                }
            
    async def start_cleanup_task(self):
        """Start background cleanup task and simulator heartbeat task"""
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Started session cleanup task.")
        if self.heartbeat_task is None or self.heartbeat_task.done():
             self.heartbeat_task = asyncio.create_task(self._simulator_heartbeat_loop())
             logger.info("Started simulator heartbeat task.")

    # In source/core/session_manager.py
    # Patch for _simulator_heartbeat_loop in source/core/session_manager.py
    async def _simulator_heartbeat_loop(self):
        """Send periodic heartbeats to active simulators managed by this pod"""
        logger.info("Simulator heartbeat loop starting.")
        while True:
            try:
                # Get active sessions potentially managed by this pod
                pod_sessions = await self.db_manager.get_sessions_with_criteria({
                    'pod_name': self.pod_name,
                    'status': SessionStatus.ACTIVE.value
                })

                heartbeat_tasks = []
                active_sim_count = 0
                for session in pod_sessions:
                    # Check if session has an active simulator and endpoint
                    sim_id = getattr(session.metadata, 'simulator_id', None)
                    sim_endpoint = getattr(session.metadata, 'simulator_endpoint', None)
                    # Use string value instead of enum
                    sim_status = getattr(session.metadata, 'simulator_status', 'NONE')

                    if sim_id and sim_endpoint and sim_status == 'RUNNING':
                        active_sim_count += 1
                        task = asyncio.create_task(
                            self._send_simulator_heartbeat(
                                session.session_id,
                                sim_id,
                                sim_endpoint
                            )
                        )
                        heartbeat_tasks.append(task)

                # Wait for all heartbeats to complete for this cycle
                if heartbeat_tasks:
                    logger.debug(f"Sending heartbeats to {len(heartbeat_tasks)} simulators.")
                    results = await asyncio.gather(*heartbeat_tasks, return_exceptions=True)
                    # Log any exceptions during heartbeat sending
                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                            # Find corresponding session/simulator ID for logging context
                            sim_id_for_log = "unknown"
                            if i < len(pod_sessions):
                                sim_id_for_log = getattr(pod_sessions[i].metadata, 'simulator_id', 'unknown')
                            logger.error(f"Exception during heartbeat for simulator {sim_id_for_log}: {result}")

                # Sleep until next heartbeat cycle
                await asyncio.sleep(15)

            except asyncio.CancelledError:
                logger.info("Simulator heartbeat loop cancelled.")
                break
            except Exception as e:
                logger.error(f"Error in simulator heartbeat loop: {e}", exc_info=True)
                await asyncio.sleep(30)  # Longer sleep on unexpected error

    async def _send_simulator_heartbeat(self, session_id, simulator_id, endpoint):
        """Send heartbeat to a specific simulator and update DB"""
        try:
            # Assuming send_heartbeat_with_ttl exists and works
            result = await self.exchange_client.send_heartbeat_with_ttl(
                endpoint,
                session_id,
                f"heartbeat-{self.pod_name}", # client_id for heartbeat
                ttl_seconds=60 # Example TTL
            )

            # Update last heartbeat timestamp in DB if successful
            if result.get('success'):
                # Use the dedicated DB method if it exists, otherwise update metadata
                # await self.db_manager.update_simulator_last_active(simulator_id, time.time())
                # OR update via metadata if no dedicated method
                 await self.db_manager.update_session_metadata(session_id, {
                     'last_simulator_heartbeat_sent': time.time()
                 })
                 logger.debug(f"Successfully sent heartbeat to simulator {simulator_id}")
                 return True
            else:
                logger.warning(f"Failed to send heartbeat to simulator {simulator_id} at {endpoint}: {result.get('error')}")
                # Consider updating simulator status in DB to ERROR if heartbeats consistently fail
                return False
        except Exception as e:
            logger.error(f"Error sending heartbeat to simulator {simulator_id} at {endpoint}: {e}", exc_info=True)
            # Consider updating simulator status in DB to ERROR here as well
            return False

    async def stop_cleanup_task(self):
        """Stop background cleanup task and heartbeat task"""
        logger.info("Stopping background tasks (cleanup, heartbeat)...")
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                logger.info("Session cleanup task cancelled.")
            except Exception as e:
                 logger.error(f"Error awaiting cancelled cleanup task: {e}")
            self.cleanup_task = None

        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                logger.info("Simulator heartbeat task cancelled.")
            except Exception as e:
                 logger.error(f"Error awaiting cancelled heartbeat task: {e}")
            self.heartbeat_task = None
        logger.info("Background tasks stopped.")

    # Patch for _cleanup_loop in source/core/session_manager.py
    async def _cleanup_loop(self):
        """Background loop for periodic cleanup tasks"""
        logger.info("Session cleanup loop starting.")
        while True:
            try:
                logger.info("Running periodic cleanup...")
                # Cleanup expired sessions (DB function handles this)
                expired_count = await self.db_manager.cleanup_expired_sessions()
                if expired_count > 0:
                    logger.info(f"Cleaned up {expired_count} expired sessions from DB.")
                    track_cleanup_operation("expired_sessions", expired_count)

                # Cleanup inactive simulators (managed by SimulatorManager)
                try:
                    inactive_sim_count = await self.simulator_manager.cleanup_inactive_simulators()
                    # Handle None return value
                    if inactive_sim_count is not None and inactive_sim_count > 0:
                        logger.info(f"Cleaned up {inactive_sim_count} inactive simulators (DB+K8s).")
                        track_cleanup_operation("inactive_simulators", inactive_sim_count)
                except Exception as e:
                    logger.error(f"Error cleaning up inactive simulators: {e}", exc_info=True)

                # Rest of the method remains the same...
                # Update active session/simulator count metrics periodically
                active_sessions = await self.db_manager.get_active_session_count()
                track_session_count(active_sessions, self.pod_name)
                active_sims = await self.db_manager.get_active_simulator_count()
                track_simulator_count(active_sims, self.pod_name)

                logger.info("Periodic cleanup finished.")
                # Sleep until next cleanup cycle (e.g., every 5 minutes)
                await asyncio.sleep(300)
            except asyncio.CancelledError:
                logger.info("Session cleanup loop cancelled.")
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Shorter interval on error before retrying

    async def _cleanup_zombie_sessions(self) -> int:
        """Identify and cleanup sessions that are still active but clients haven't connected in a long time"""
        zombie_count = 0
        try:
            logger.debug("Checking for zombie sessions...")
            # Define thresholds for zombie detection
            # No heartbeat received for 10x interval (e.g., 10 * 10s = 100s)
            heartbeat_missing_threshold = time.time() - (config.websocket.heartbeat_interval * 10)
            # No WS connection established/active for 1 hour
            connection_missing_threshold = time.time() - 3600

            # Get all potentially active sessions from the database
            # Fetch sessions that are marked ACTIVE but might be zombies
            potentially_active_sessions = await self.db_manager.get_sessions_with_criteria({
                'status': SessionStatus.ACTIVE.value
            })

            if not potentially_active_sessions:
                 logger.debug("No active sessions found to check for zombies.")
                 return 0

            for session in potentially_active_sessions:
                # Basic check: If DB last_active is very recent, skip
                if session.last_active > heartbeat_missing_threshold:
                    continue

                # Deeper check: Look at metadata for last WS connection time
                # Safely get metadata attributes
                metadata = session.metadata # Already a SessionMetadata object
                last_ws_connection_ts = getattr(metadata, 'last_ws_connection', None)
                # Assuming SSE might exist based on original code, handle defensively
                last_sse_connection_ts = getattr(metadata, 'last_sse_connection', None)

                # *** FIX: Default None to 0.0 before comparison ***
                last_ws_connection = last_ws_connection_ts if last_ws_connection_ts is not None else 0.0
                last_sse_connection = last_sse_connection_ts if last_sse_connection_ts is not None else 0.0

                # If there was a connection recently (WS or SSE), skip
                if max(last_ws_connection, last_sse_connection) > connection_missing_threshold:
                    continue

                # If session is old and has no recent WS/SSE connection, consider it a zombie
                # Add extra check: only cleanup if session is older than, say, 5 minutes
                if time.time() - session.created_at < 300:
                    continue # Skip very new sessions

                # This session appears to be a zombie
                logger.info(f"Identified zombie session {session.session_id} (User: {session.user_id}). "
                            f"Last DB Active: {session.last_active}, Last WS Conn: {last_ws_connection_ts}")

                # Stop any running simulators associated with this zombie session
                sim_id = getattr(metadata, 'simulator_id', None)
                sim_status = getattr(metadata, 'simulator_status', SimulatorStatus.NONE)
                if sim_id and sim_status != SimulatorStatus.STOPPED:
                    logger.info(f"Stopping simulator {sim_id} for zombie session {session.session_id}")
                    try:
                        # Use force=True as we know the session is defunct
                        await self.stop_simulator(session.session_id, token=None, force=True)
                    except Exception as e:
                        logger.error(f"Error stopping simulator {sim_id} for zombie session {session.session_id}: {e}", exc_info=True)

                # Mark session as expired in the database
                logger.info(f"Marking zombie session {session.session_id} as EXPIRED.")
                await self.db_manager.update_session_status(session.session_id, SessionStatus.EXPIRED.value)
                zombie_count += 1

        except Exception as e:
            # Log the error but allow the cleanup loop to continue
            logger.error(f"Error during zombie session cleanup: {e}", exc_info=True)

        if zombie_count > 0:
            logger.info(f"Finished cleaning up {zombie_count} zombie sessions.")
        else:
            logger.debug("No zombie sessions found needing cleanup.")

        return zombie_count


    async def transfer_session_ownership(self, session_id: str, new_pod_name: str) -> bool:
        """Transfer ownership of a session to another pod during migration"""
        with optional_trace_span(self.tracer, "transfer_session_ownership") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("new_pod_name", new_pod_name)

            session = await self.db_manager.get_session(session_id)
            if not session:
                span.set_attribute("error", "Session not found")
                logger.warning(f"Attempted to transfer non-existent session {session_id}")
                return False

            # Get current pod name safely
            current_pod = getattr(session.metadata, 'pod_name', 'unknown')
            span.set_attribute("current_pod", current_pod)

            # Record handoff in progress
            await self.db_manager.update_session_metadata(session_id, {
                'pod_transferred': True,
                'previous_pod': current_pod,
                'pod_name': new_pod_name, # Update pod_name in metadata
                'transfer_timestamp': time.time()
            })
            logger.info(f"Transferred session {session_id} ownership from {current_pod} to {new_pod_name}")

            # Notify clients of migration via WebSocket if manager exists
            if self.websocket_manager:
                await self.websocket_manager.broadcast_to_session(session_id, {
                    'type': 'session_migration',
                    'new_pod': new_pod_name # Inform client about the new pod (optional)
                })

            # Publish migration event to Redis for other pods if Redis exists
            if self.redis:
                try:
                    await self.redis.publish('session_events', json.dumps({
                        'type': 'session_migrated',
                        'session_id': session_id,
                        'previous_pod': current_pod,
                        'new_pod': new_pod_name,
                        'timestamp': time.time()
                    }))
                except Exception as e:
                    logger.error(f"Failed to publish session migration event to Redis for {session_id}: {e}")

            return True

    # Note: _run_simulator_heartbeat_task seems redundant with _simulator_heartbeat_loop
    # Consolidating into _simulator_heartbeat_loop

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
                active_sessions = await self.db_manager.get_active_user_sessions(user_id)
                for old_session in active_sessions:
                    logger.warning(f"User {user_id} has existing active session {old_session.session_id}. Ending it.")
                    span.add_event("Ending existing session", {"old_session_id": old_session.session_id})
                    # Force stop the simulator associated with the old session
                    await self.stop_simulator(old_session.session_id, token=token, force=True) # Use force=True
                    # Mark the old session as expired in DB
                    await self.db_manager.update_session_status(old_session.session_id, SessionStatus.EXPIRED.value)
                    # Optionally notify the old client via WebSocket if possible (difficult without WS handle)
                # -----------------------------------------

                # Create new session in DB
                session_id, is_new = await self.db_manager.create_session(user_id, ip_address)
                span.set_attribute("session_id", session_id)
                span.set_attribute("is_new", is_new) # Should always be true after cleanup

                if not session_id:
                     # This case should ideally not happen if DB call is robust
                     logger.error(f"Failed to create session record in DB for user {user_id}")
                     span.set_attribute("error", "DB session creation failed")
                     return None, False

                # Set essential metadata including the validated device_id and current pod
                await self.db_manager.update_session_metadata(session_id, {
                    'pod_name': self.pod_name,
                    'ip_address': ip_address,
                    'device_id': device_id, # Store the device ID associated with this session
                    'frontend_connections': 0, # Initialize connection count
                    'reconnect_count': 0
                })

                # Track session creation metric
                track_session_operation("create")

                # Publish session creation event if Redis is available
                if self.redis:
                    try:
                        await self.redis.publish('session_events', json.dumps({
                            'type': 'session_created',
                            'session_id': session_id,
                            'user_id': user_id,
                            'device_id': device_id,
                            'pod_name': self.pod_name,
                            'timestamp': time.time()
                        }))
                    except Exception as e:
                         logger.error(f"Failed to publish session creation event to Redis for {session_id}: {e}")


                # Update active session count metric
                active_session_count = await self.db_manager.get_active_session_count()
                track_session_count(active_session_count, self.pod_name)

                logger.info(f"Successfully created new session {session_id} for user {user_id}, device {device_id}")
                return session_id, is_new # is_new should be True

            except Exception as e:
                logger.error(f"Error during session creation for user {user_id}: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return None, False

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
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
                session = await self.db_manager.get_session(session_id) # Fetches Session object

                if not session:
                    span.set_attribute("session_found", False)
                    logger.debug(f"Session {session_id} not found in DB.")
                    return None

                # Check if session is expired (should be handled by get_session query, but double check)
                if session.is_expired():
                     span.set_attribute("session_expired", True)
                     logger.warning(f"get_session retrieved an expired session {session_id}")
                     # Optionally mark as expired here if DB query failed
                     # await self.db_manager.update_session_status(session_id, SessionStatus.EXPIRED.value)
                     return None

                span.set_attribute("session_found", True)
                span.set_attribute("user_id", session.user_id)
                # Convert Session object to dictionary for return
                return session.to_dict()

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
             validation = await self.auth_client.validate_token(token)
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
             session = await self.db_manager.get_session(session_id) # Fetches Session object
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
                 # Optionally mark as expired here if DB query failed
                 # await self.db_manager.update_session_status(session_id, SessionStatus.EXPIRED.value)
                 return None

             # 5. If device_id provided, validate it matches the one stored in metadata
             if device_id:
                 stored_device_id = getattr(session.metadata, 'device_id', None)
                 span.set_attribute("stored_device_id", stored_device_id)
                 if stored_device_id != device_id:
                     logger.warning(f"Device ID mismatch for session {session_id}. Expected: {stored_device_id}, Got: {device_id}")
                     span.set_attribute("validation_error", "Device ID mismatch")
                     return None # Strict check: if device ID is provided, it MUST match

             # 6. Validation successful, update session activity
             # Use the dedicated DB method for this
             update_success = await self.db_manager.update_session_activity(session_id)
             if not update_success:
                  logger.warning(f"Failed to update session activity for {session_id} after validation.")
                  # Decide if this should be a validation failure - perhaps not, log and continue.
                  span.set_attribute("activity_update_failed", True)

             span.set_attribute("validation_successful", True)
             logger.debug(f"Session {session_id} validated successfully for user {user_id}.")
             return user_id # Return user ID on successful validation

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
            success = await self.db_manager.update_session_activity(session_id)
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
            user_id = await self.validate_session(session_id, token) # Validation updates activity if successful
            span.set_attribute("user_id", user_id)
            span.set_attribute("session_valid", user_id is not None)

            if not user_id:
                error_msg = "Invalid session or token for ending session."
                span.set_attribute("error", error_msg)
                logger.warning(f"Attempt to end session {session_id} failed validation.")
                return False, error_msg

            try:
                # 2. Get current session details (needed for simulator info and lifetime metric)
                session = await self.db_manager.get_session(session_id)
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
                    sim_stopped, sim_stop_error = await self.stop_simulator(session_id, token=token, force=True)
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
                success = await self.db_manager.update_session_status(session_id, SessionStatus.EXPIRED.value)

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
                active_session_count = await self.db_manager.get_active_session_count()
                track_session_count(active_session_count, self.pod_name)

                # 7. Publish session end event if Redis is available
                if self.redis:
                     try:
                         await self.redis.publish('session_events', json.dumps({
                             'type': 'session_ended',
                             'session_id': session_id,
                             'user_id': user_id,
                             'pod_name': self.pod_name,
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

    async def update_connection_quality(
        self,
        session_id: str,
        token: str,
        metrics: Dict[str, Any]
    ) -> Tuple[str, bool]:
        """
        Update connection quality metrics based on client report.

        Args:
            session_id: The session ID
            token: Authentication token
            metrics: Connection metrics dict (latency_ms, missed_heartbeats, connection_type)

        Returns:
            Tuple of (quality_string, reconnect_recommended_bool)
        """
        with optional_trace_span(self.tracer, "update_connection_quality") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("metrics.latency_ms", metrics.get('latency_ms', -1))
            span.set_attribute("metrics.missed_heartbeats", metrics.get('missed_heartbeats', -1))
            span.set_attribute("metrics.connection_type", metrics.get('connection_type', 'unknown'))

            # 1. Validate session
            user_id = await self.validate_session(session_id, token) # Validation updates activity
            span.set_attribute("user_id", user_id)
            span.set_attribute("session_valid", user_id is not None)

            if not user_id:
                span.set_attribute("error", "Invalid session or token")
                return "unknown", False

            try:
                # 2. Get session details (optional, could potentially update DB directly)
                # session = await self.db_manager.get_session(session_id)
                # if not session: # Should not happen if validation passed
                #      span.set_attribute("error", "Session vanished after validation")
                #      return "unknown", False

                # 3. Determine quality based on metrics (logic moved from Session model)
                latency_ms = metrics.get('latency_ms', 0)
                missed_heartbeats = metrics.get('missed_heartbeats', 0)
                quality = ConnectionQuality.GOOD # Default
                reconnect_recommended = False

                if missed_heartbeats >= 3:
                    quality = ConnectionQuality.POOR
                    reconnect_recommended = True
                elif missed_heartbeats > 0 or latency_ms > 500:
                    quality = ConnectionQuality.DEGRADED
                    # Reconnect not usually recommended just for degraded
                    reconnect_recommended = False
                # else: quality remains GOOD

                span.set_attribute("calculated_quality", quality.value)
                span.set_attribute("reconnect_recommended", reconnect_recommended)

                # 4. Update database metadata
                update_success = await self.db_manager.update_session_metadata(session_id, {
                    'connection_quality': quality.value, # Store enum value as string
                    'heartbeat_latency': latency_ms,
                    'missed_heartbeats': missed_heartbeats,
                    'last_quality_update': time.time() # Track update time
                })

                if not update_success:
                     logger.warning(f"Failed to update session metadata for connection quality on {session_id}")
                     span.set_attribute("db_update_failed", True)
                     # Don't fail the call, but log it

                # 5. Track connection quality metric
                track_connection_quality(quality.value, self.pod_name)

                return quality.value, reconnect_recommended
            except Exception as e:
                logger.error(f"Error updating connection quality for session {session_id}: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return "unknown", False

    async def start_simulator(self, session_id: str, token: str, symbols: List[str] = None) -> Tuple[Optional[str], Optional[str], str]:
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
            user_id = await self.validate_session(session_id, token) # Validation updates activity
            span.set_attribute("user_id", user_id)
            span.set_attribute("session_valid", user_id is not None)

            if not user_id:
                error_msg = "Invalid session or token for starting simulator."
                span.set_attribute("error", error_msg)
                return None, None, error_msg

            try:
                # 2. Get current session details
                session = await self.db_manager.get_session(session_id)
                if not session: # Should not happen
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
                simulator_obj, error = await self.simulator_manager.create_simulator(
                    session_id,
                    user_id,
                    symbols # Pass symbols if provided
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
                new_status = simulator_obj.status # Should be STARTING or RUNNING
                span.set_attribute("new_simulator_id", new_sim_id)
                span.set_attribute("new_simulator_endpoint", new_endpoint)
                span.set_attribute("new_simulator_status", new_status.value)


                # 5. Update session metadata with the new simulator details
                update_success = await self.db_manager.update_session_metadata(session_id, {
                    'simulator_id': new_sim_id,
                    'simulator_endpoint': new_endpoint,
                    'simulator_status': new_status.value # Store enum value
                })
                if not update_success:
                     logger.warning(f"Failed to update session metadata after starting simulator {new_sim_id}")
                     span.set_attribute("metadata_update_failed", True)
                     # Continue, but log the issue

                # 6. Publish simulator started event if Redis is available
                if self.redis:
                    try:
                        await self.redis.publish('session_events', json.dumps({
                            'type': 'simulator_started',
                            'session_id': session_id,
                            'simulator_id': new_sim_id,
                            'pod_name': self.pod_name,
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

    async def get_user_from_token(self, token: str) -> Optional[str]:
        """Extract user ID from token via AuthClient"""
        validation = await self.auth_client.validate_token(token)
        if validation.get('valid', False):
            return validation.get('userId')
        return None

    # This method seems less relevant if create_session enforces single session
    # async def get_or_create_user_session(self, user_id: str, token: str) -> Optional[str]:
    #     """Get user's active session or create a new one"""
    #     # Check for existing active session
    #     active_sessions = await self.db_manager.get_active_user_sessions(user_id)
    #
    #     # Return first active session if exists
    #     if active_sessions:
    #         return active_sessions[0].session_id
    #
    #     # Create new session - Requires device_id now
    #     # Need to rethink how this is called if device_id isn't available
    #     # session_id, _ = await self.create_session(user_id, "unknown_device", token) # Placeholder device_id
    #     # return session_id
    #     logger.warning("get_or_create_user_session called without device_id, cannot create session.")
    #     return None # Cannot create without device_id


    async def stop_simulator(self, session_id: str, token: Optional[str] = None, force: bool = False) -> Tuple[bool, str]:
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
                user_id = await self.validate_session(session_id, token) # Validation updates activity
                span.set_attribute("user_id", user_id)
                span.set_attribute("session_valid", user_id is not None)
                if not user_id:
                    error_msg = "Invalid session or token for stopping simulator."
                    span.set_attribute("error", error_msg)
                    return False, error_msg
            # If forcing, we proceed without user_id validation here

            try:
                # 1. Get session details to find the simulator ID
                session = await self.db_manager.get_session(session_id)
                if not session:
                    # If forcing, session might already be gone, log and return success
                    if force:
                         logger.warning(f"Session {session_id} not found during forced simulator stop (might be already cleaned up).")
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
                     return True, "" # Idempotent


                # 3. Stop simulator via SimulatorManager
                logger.info(f"Requesting simulator stop for {simulator_id} (Session: {session_id}, Force: {force})")
                # SimulatorManager handles DB updates and K8s deletion
                success, error = await self.simulator_manager.stop_simulator(simulator_id)
                span.set_attribute("simulator_stop_success", success)

                if not success:
                    logger.error(f"Failed to stop simulator {simulator_id} via manager: {error}")
                    span.set_attribute("error", f"Simulator stop failed: {error}")
                    # Even if manager fails, update metadata if possible
                    # Fall through to update metadata

                # 4. Update session metadata to reflect simulator stopped status
                # Ensure simulator_id is cleared even if stop failed to prevent reuse
                update_success = await self.db_manager.update_session_metadata(session_id, {
                    'simulator_status': SimulatorStatus.STOPPED.value,
                    'simulator_id': None, # Clear simulator ID
                    'simulator_endpoint': None # Clear endpoint
                })
                if not update_success:
                     logger.warning(f"Failed to update session metadata after stopping simulator {simulator_id}")
                     span.set_attribute("metadata_update_failed", True)
                     # Don't fail the call if simulator stop itself succeeded

                # 5. Publish simulator stopped event if Redis is available
                if self.redis:
                    # Get user_id if forcing and session was found
                    if force and not user_id:
                        user_id = session.user_id

                    try:
                        await self.redis.publish('session_events', json.dumps({
                            'type': 'simulator_stopped',
                            'session_id': session_id,
                            'simulator_id': simulator_id, # Include ID in event
                            'user_id': user_id, # Include user if available
                            'pod_name': self.pod_name,
                            'timestamp': time.time(),
                            'forced': force
                        }))
                    except Exception as e:
                         logger.error(f"Failed to publish simulator stop event to Redis for {session_id}: {e}")

                logger.info(f"Simulator stop process completed for {simulator_id} (Session: {session_id}). Success: {success}")
                # Return overall success based on the simulator manager's result
                return success, error if not success else ""

            except Exception as e:
                logger.error(f"Unexpected error stopping simulator for session {session_id}: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return False, f"Server error stopping simulator: {str(e)}"

    async def reconnect_session(self, session_id: str, token: str, device_id: str, attempt: int = 1) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Handle session reconnection attempt. Validates session/token/device,
        checks simulator status, and returns necessary info.

        Args:
            session_id: The session ID
            token: Authentication token
            device_id: Device ID attempting to reconnect
            attempt: Reconnection attempt number

        Returns:
            Tuple of (session_dict_for_client, error_message)
            The session_dict contains non-sensitive info needed by the client.
        """
        with optional_trace_span(self.tracer, "reconnect_session") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("device_id", device_id)
            span.set_attribute("reconnect_attempt", attempt)

            # 1. Validate session, token, AND device_id
            user_id = await self.validate_session(session_id, token, device_id) # Pass device_id
            span.set_attribute("user_id", user_id)
            span.set_attribute("session_valid", user_id is not None)

            if not user_id:
                error_msg = "Invalid session, token, or deviceId for reconnection."
                span.set_attribute("error", error_msg)
                return None, error_msg

            try:
                # 2. Get session details again (validation already updated activity)
                session = await self.db_manager.get_session(session_id)
                if not session: # Should not happen
                    logger.error(f"Session {session_id} passed validation but not found for reconnect.")
                    span.set_attribute("error", "Session vanished after validation")
                    return None, "Session not found unexpectedly"

                metadata = session.metadata
                simulator_id = getattr(metadata, 'simulator_id', None)
                sim_status = getattr(metadata, 'simulator_status', SimulatorStatus.NONE)
                reconnect_count = getattr(metadata, 'reconnect_count', 0)
                span.set_attribute("simulator_id", simulator_id)
                span.set_attribute("simulator_status", sim_status.value if sim_status else 'NONE')

                # 3. Check if simulator needs restart
                simulator_needs_restart = False
                if simulator_id:
                    # Check simulator status via manager (which might check K8s/gRPC)
                    # This provides a more up-to-date status than just DB metadata
                    status_info = await self.simulator_manager.get_simulator_status(simulator_id)
                    current_k8s_status = status_info.get('k8s_status', 'UNKNOWN') # Get K8s status if available
                    current_db_status = status_info.get('status', 'UNKNOWN') # Get DB status

                    # If K8s reports not running/found, or DB status is stopped/error, it needs restart
                    if current_k8s_status not in ["RUNNING", "PENDING"] or current_db_status in [SimulatorStatus.STOPPED.value, SimulatorStatus.ERROR.value]:
                         simulator_needs_restart = True
                         logger.info(f"Simulator {simulator_id} for session {session_id} needs restart. K8s: {current_k8s_status}, DB: {current_db_status}")
                         span.add_event("Simulator needs restart", {"k8s_status": current_k8s_status, "db_status": current_db_status})
                         # Optionally clean up metadata if simulator is confirmed dead
                         # await self.db_manager.update_session_metadata(session_id, {
                         #    'simulator_status': SimulatorStatus.STOPPED.value,
                         #    'simulator_id': None,
                         #    'simulator_endpoint': None
                         # })
                    else:
                         # Update metadata status if manager check revealed a change
                         if current_db_status != sim_status.value:
                              await self.db_manager.update_session_metadata(session_id, {'simulator_status': current_db_status})
                              sim_status = SimulatorStatus(current_db_status) # Update local var

                # 4. Update session metadata for reconnection attempt
                new_reconnect_count = reconnect_count + 1
                update_success = await self.db_manager.update_session_metadata(session_id, {
                    'reconnect_count': new_reconnect_count,
                    'last_reconnect': time.time()
                })
                if not update_success:
                     logger.warning(f"Failed to update session metadata for reconnect on {session_id}")
                     span.set_attribute("metadata_update_failed", True)

                # Track reconnection metric
                track_client_reconnection(new_reconnect_count)
                span.set_attribute("new_reconnect_count", new_reconnect_count)

                # 5. Prepare response dictionary for the client (non-sensitive info)
                client_response = {
                    # 'sessionId': session_id, # Don't send back
                    'simulatorStatus': sim_status.value if sim_status else 'NONE',
                    'simulatorNeedsRestart': simulator_needs_restart,
                    'podName': getattr(metadata, 'pod_name', self.pod_name), # Current pod handling it
                    # Add any other non-sensitive state the client might need on reconnect
                }

                logger.info(f"Session {session_id} reconnected successfully (Attempt: {attempt}). Sim Status: {client_response['simulatorStatus']}, Needs Restart: {simulator_needs_restart}")
                return client_response, ""

            except Exception as e:
                logger.error(f"Error reconnecting session {session_id}: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return None, f"Server error reconnecting session: {str(e)}"

