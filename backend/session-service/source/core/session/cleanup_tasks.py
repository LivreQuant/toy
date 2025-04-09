"""
Background cleanup tasks for the session service.
Handles cleanup of expired sessions, inactive simulators, and heartbeat functions.
"""
import logging
import time
import asyncio
from typing import Dict, Any, Optional, List
from opentelemetry import trace
from source.config import config
from source.models.simulator import SimulatorStatus
from source.utils.metrics import track_cleanup_operation, track_session_count, track_simulator_count
from source.utils.tracing import optional_trace_span

logger = logging.getLogger('cleanup_tasks')

class CleanupTasks:
    """Handles background cleanup tasks for session service"""
    
    def __init__(self, session_manager):
        """
        Initialize with reference to session manager
        
        Args:
            session_manager: Parent SessionManager instance
        """
        self.manager = session_manager
        self.tracer = trace.get_tracer("cleanup_tasks")
        
    async def run_cleanup_loop(self):
        """Background loop for periodic cleanup tasks"""
        logger.info("Session cleanup loop starting.")
        while True:
            try:
                logger.info("Running periodic cleanup...")
                # Cleanup expired sessions (DB function handles this)
                expired_count = await self.manager.db_manager.cleanup_expired_sessions()
                if expired_count > 0:
                    logger.info(f"Cleaned up {expired_count} expired sessions from DB.")
                    track_cleanup_operation("expired_sessions", expired_count)

                # Cleanup inactive simulators (managed by SimulatorManager)
                try:
                    inactive_sim_count = await self.manager.simulator_manager.cleanup_inactive_simulators()
                    # Handle None return value
                    if inactive_sim_count is not None and inactive_sim_count > 0:
                        logger.info(f"Cleaned up {inactive_sim_count} inactive simulators (DB+K8s).")
                        track_cleanup_operation("inactive_simulators", inactive_sim_count)
                except Exception as e:
                    logger.error(f"Error cleaning up inactive simulators: {e}", exc_info=True)

                # Cleanup zombie sessions
                zombie_count = await self._cleanup_zombie_sessions()
                if zombie_count > 0:
                    logger.info(f"Cleaned up {zombie_count} zombie sessions")
                    track_cleanup_operation("zombie_sessions", zombie_count)

                # Update active session/simulator count metrics periodically
                active_sessions = await self.manager.db_manager.get_active_session_count()
                track_session_count(active_sessions, self.manager.pod_name)
                active_sims = await self.manager.db_manager.get_active_simulator_count()
                track_simulator_count(active_sims, self.manager.pod_name)

                logger.info("Periodic cleanup finished.")
                # Sleep until next cleanup cycle (e.g., every 5 minutes)
                await asyncio.sleep(300)
            except asyncio.CancelledError:
                logger.info("Session cleanup loop cancelled.")
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Shorter interval on error before retrying
    
    async def run_simulator_heartbeat_loop(self):
        """Send periodic heartbeats to active simulators managed by this pod"""
        logger.info("Simulator heartbeat loop starting.")
        while True:
            try:
                # Get active sessions potentially managed by this pod
                pod_sessions = await self.manager.db_manager.get_sessions_with_criteria({
                    'pod_name': self.manager.pod_name,
                    'status': 'ACTIVE'
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
            result = await self.manager.exchange_client.send_heartbeat_with_ttl(
                endpoint,
                session_id,
                f"heartbeat-{self.manager.pod_name}", # client_id for heartbeat
                ttl_seconds=60 # Example TTL
            )

            # Update last heartbeat timestamp in DB if successful
            if result.get('success'):
                # Use the dedicated DB method if it exists, otherwise update metadata
                # await self.db_manager.update_simulator_last_active(simulator_id, time.time())
                # OR update via metadata if no dedicated method
                 await self.manager.db_manager.update_session_metadata(session_id, {
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
            potentially_active_sessions = await self.manager.db_manager.get_sessions_with_criteria({
                'status': 'ACTIVE'
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
                        await self.manager.simulator_ops.stop_simulator(session.session_id, token=None, force=True)
                    except Exception as e:
                        logger.error(f"Error stopping simulator {sim_id} for zombie session {session.session_id}: {e}", exc_info=True)

                # Mark session as expired in the database
                logger.info(f"Marking zombie session {session.session_id} as EXPIRED.")
                await self.manager.db_manager.update_session_status(session.session_id, 'EXPIRED')
                zombie_count += 1

        except Exception as e:
            # Log the error but allow the cleanup loop to continue
            logger.error(f"Error during zombie session cleanup: {e}", exc_info=True)

        if zombie_count > 0:
            logger.info(f"Finished cleaning up {zombie_count} zombie sessions.")
        else:
            logger.debug("No zombie sessions found needing cleanup.")

        return zombie_count