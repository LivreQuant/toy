"""
Background cleanup tasks for the session service.
Handles cleanup of expired sessions, inactive simulators, and heartbeat functions.
"""
import logging
import time
import asyncio
from opentelemetry import trace

from source.config import config
from source.utils.event_bus import event_bus
from source.models.simulator import SimulatorStatus
from source.utils.metrics import track_cleanup_operation, track_session_count, track_simulator_count
from source.utils.tracing import optional_trace_span

logger = logging.getLogger('session_tasks')


class SessionTasks:
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
        """Check simulators in STARTING state and verify if they're ready"""
        try:
            if hasattr(self.manager, 'simulator_manager') and self.manager.simulator_manager:
                # Get simulators in STARTING state
                starting_simulators = await self.manager.simulator_manager.get_simulators_with_status(SimulatorStatus.STARTING)

                if not starting_simulators:
                    return

                logger.debug(f"Checking {len(starting_simulators)} simulators in STARTING state")

                for simulator in starting_simulators:
                    # Skip simulators that have been in STARTING state for too short a time
                    # Give them at least 10 seconds to initialize
                    if time.time() - simulator.last_active < 10:
                        continue

                    # Check if simulator is ready
                    is_ready = await self.manager.simulator_manager.check_simulator_ready(simulator.simulator_id)

                    if is_ready:
                        logger.info(f"Simulator {simulator.simulator_id} is now RUNNING")

                        # Also update session metadata
                        try:
                            await self.manager.store.session_store.update_session_metadata(simulator.session_id, {
                                'simulator_status': SimulatorStatus.RUNNING.value
                            })

                            # Publish simulator ready event
                            await event_bus.publish('simulator_ready',
                                                  session_id=simulator.session_id,
                                                  simulator_id=simulator.simulator_id,
                                                  endpoint=simulator.endpoint)

                        except Exception as e:
                            logger.error(f"Failed to update session metadata for simulator {simulator.simulator_id}: {e}")

        except Exception as e:
            logger.error(f"Error checking starting simulators: {e}", exc_info=True)

    async def run_cleanup_loop(self):
        """Background loop for periodic cleanup tasks"""
        logger.info("Session cleanup loop starting.")
        while True:
            try:
                logger.info("Running periodic cleanup...")
                # Cleanup expired sessions (DB function handles this)
                expired_count = await self.manager.store.session_store.cleanup_expired_sessions()
                if expired_count > 0:
                    logger.info(f"Cleaned up {expired_count} expired sessions from DB.")
                    track_cleanup_operation("expired_sessions", expired_count)

                    # Publish cleanup event
                    await event_bus.publish('sessions_cleaned_up',
                                          count=expired_count,
                                          reason="expired")

                # Cleanup inactive simulators (managed by SimulatorManager)
                if hasattr(self.manager, 'simulator_manager') and self.manager.simulator_manager:
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

                    # Publish zombie cleanup event
                    await event_bus.publish('sessions_cleaned_up',
                                          count=zombie_count,
                                          reason="zombie")

                # Update active session/simulator count metrics periodically
                active_sessions = await self.manager.store.session_store.get_active_session_count()
                track_session_count(active_sessions, self.manager.pod_name)

                if hasattr(self.manager, 'simulator_manager') and self.manager.simulator_manager:
                    active_sims = await self.manager.simulator_manager.get_active_simulator_count()
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
            potentially_active_sessions = await self.manager.store.session_store.get_sessions_with_criteria({
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
                metadata = session.metadata  # Already a SessionMetadata object
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
                    continue  # Skip very new sessions

                # This session appears to be a zombie
                logger.info(f"Identified zombie session {session.session_id} (User: {session.user_id}). "
                            f"Last DB Active: {session.last_active}, Last WS Conn: {last_ws_connection_ts}")

                # Publish zombie session detected event
                await event_bus.publish('zombie_session_detected',
                                      session_id=session.session_id,
                                      user_id=session.user_id)

                # Stop any running simulators associated with this zombie session
                sim_id = getattr(metadata, 'simulator_id', None)
                sim_status = getattr(metadata, 'simulator_status', SimulatorStatus.NONE)
                if sim_id and sim_status != SimulatorStatus.STOPPED:
                    logger.info(f"Stopping simulator {sim_id} for zombie session {session.session_id}")
                    try:
                        # Use force=True as we know the session is defunct
                        await self.manager.stop_simulator(session.session_id, token=None, force=True)
                    except Exception as e:
                        logger.error(f"Error stopping simulator {sim_id} for zombie session {session.session_id}: {e}",
                                     exc_info=True)

                # Mark session as expired in the database
                logger.info(f"Marking zombie session {session.session_id} as EXPIRED.")
                await self.manager.store.session_store.update_session_status(session.session_id, 'EXPIRED')

                # Publish session expired event
                await event_bus.publish('session_expired',
                                      session_id=session.session_id,
                                      reason="zombie")

                zombie_count += 1

        except Exception as e:
            # Log the error but allow the cleanup loop to continue
            logger.error(f"Error during zombie session cleanup: {e}", exc_info=True)

        if zombie_count > 0:
            logger.info(f"Finished cleaning up {zombie_count} zombie sessions.")
        else:
            logger.debug("No zombie sessions found needing cleanup.")

        return zombie_count

    async def run_simulator_heartbeat_loop(self):
        """Send periodic heartbeats to active simulators managed by this pod"""
        logger.info("Simulator heartbeat loop starting.")
        while True:
            try:
                # Check simulators in STARTING state
                await self._check_starting_simulators()

                # Get active sessions potentially managed by this pod
                pod_sessions = await self.manager.store.session_store.get_sessions_with_criteria({
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
                        if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
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
            # Assuming send_heartbeat exists and works
            result = await self.manager.exchange_client.send_heartbeat(
                endpoint,
                session_id,
                f"heartbeat-{self.manager.pod_name}",  # client_id for heartbeat
            )

            # Update last heartbeat timestamp in DB if successful
            if result.get('success'):
                # Use the dedicated DB method if it exists, otherwise update metadata
                # await self.db_manager.update_simulator_last_active(simulator_id, time.time())
                # OR update via metadata if no dedicated method
                await self.manager.store.session_store.update_session_metadata(session_id, {
                    'last_simulator_heartbeat_sent': time.time()
                })

                if hasattr(self.manager, 'simulator_manager') and self.manager.simulator_manager:
                    await self.manager.simulator_manager.update_simulator_activity(simulator_id)

                logger.debug(f"Successfully sent heartbeat to simulator {simulator_id}")

                # Publish successful heartbeat event
                await event_bus.publish('simulator_heartbeat_success',
                                      session_id=session_id,
                                      simulator_id=simulator_id)

                return True
            else:
                logger.warning(
                    f"Failed to send heartbeat to simulator {simulator_id} at {endpoint}: {result.get('error')}")

                # Publish heartbeat failure event
                await event_bus.publish('simulator_heartbeat_failed',
                                      session_id=session_id,
                                      simulator_id=simulator_id,
                                      error=result.get('error', 'Unknown error'))

                # Consider updating simulator status in DB to ERROR if heartbeats consistently fail
                return False
        except Exception as e:
            logger.error(f"Error sending heartbeat to simulator {simulator_id} at {endpoint}: {e}", exc_info=True)

            # Publish heartbeat error event
            await event_bus.publish('simulator_heartbeat_error',
                                  session_id=session_id,
                                  simulator_id=simulator_id,
                                  error=str(e))

            # Consider updating simulator status in DB to ERROR here as well
            return False

    async def cleanup_pod_sessions(self, pod_name):
        """Clean up sessions and simulators associated with this pod before shutdown"""
        logger.info("Starting cleanup of sessions managed by this pod.")
        try:
            pod_sessions = await self.manager.store.session_store.get_sessions_with_criteria({
                'pod_name': pod_name
                # Add 'status': 'active' or similar if applicable
            })

            if not pod_sessions:
                logger.info("No active sessions found for this pod to clean up.")
                return

            logger.info(f"Found {len(pod_sessions)} sessions potentially managed by this pod. Initiating cleanup...")

            simulator_tasks = []
            sessions_to_update = []

            for session_data in pod_sessions:
                # Access metadata safely, assuming it might be None or not a dict
                metadata = session_data.metadata

                session_id = session_data.session_id
                if not session_id:
                    continue

                simulator_id = getattr(metadata, 'simulator_id', None)
                simulator_status = getattr(metadata, 'simulator_status', None)
                simulator_endpoint = getattr(metadata, 'simulator_endpoint', None)

                sessions_to_update.append(session_id)

                # Check if session has a simulator running or starting
                if simulator_id and simulator_status not in [SimulatorStatus.STOPPED.value,
                                                             SimulatorStatus.ERROR.value,
                                                             None]:
                    logger.info(f"Scheduling simulator {simulator_id} for session {session_id} for shutdown.")
                    task = asyncio.create_task(
                        self._stop_simulator_with_fallbacks(
                            session_id,
                            simulator_id,
                            simulator_endpoint
                        )
                    )
                    simulator_tasks.append(task)
                else:
                    logger.debug(f"No active simulator found for session {session_id} to stop.")

            # Wait for simulator shutdowns with timeout
            if simulator_tasks:
                logger.info(f"Waiting for {len(simulator_tasks)} simulator shutdown tasks...")
                # Allow timeout for graceful shutdowns
                done, pending = await asyncio.wait(
                    simulator_tasks,
                    timeout=config.server.shutdown_timeout - 2.0,  # Allow margin
                    return_when=asyncio.ALL_COMPLETED
                )

                logger.info(f"Completed {len(done)} simulator shutdown tasks.")
                if pending:
                    logger.warning(f"{len(pending)} simulator shutdown tasks timed out or were cancelled.")
                    # Cancel any pending tasks explicitly
                    for task in pending:
                        task.cancel()
                        try:
                            await task  # Allow cancellation to propagate
                        except asyncio.CancelledError:
                            pass
                        except Exception as e:
                            logger.error(f"Error awaiting cancelled simulator task: {e}", exc_info=True)
                    # Optionally add direct K8s delete here for timed-out ones if needed

            # Update all affected session states in DB
            logger.info(f"Updating metadata for {len(sessions_to_update)} sessions to mark pod termination.")
            update_metadata = {
                'pod_terminating': True,
                'termination_time': time.time(),
                # Mark simulator as stopped if we attempted cleanup, even if it failed/timed out
                # K8s garbage collection should handle orphaned resources eventually
                'simulator_status': SimulatorStatus.STOPPED.value
            }

            # Batch update sessions if DB manager supports it, otherwise loop
            for s_id in sessions_to_update:
                try:
                    await self.manager.store.session_store.update_session_metadata(s_id, update_metadata)

                    # Publish pod terminating event
                    await event_bus.publish('pod_terminating',
                                          session_id=s_id,
                                          pod_name=pod_name)

                except Exception as e:
                    logger.error(f"Error updating session {s_id} metadata during shutdown: {e}", exc_info=True)

            logger.info("Session cleanup phase complete.")

        except Exception as e:
            logger.error(f"Error during _cleanup_pod_sessions: {e}", exc_info=True)

    async def _stop_simulator_with_fallbacks(self, session_id, simulator_id, endpoint):
        """Try multiple approaches to ensure simulator is stopped"""
        try:
            # First attempt: Use simulator_ops
            success, error = await self.manager.stop_simulator(session_id, token=None, force=True)

            if success:
                logger.info(f"Successfully stopped simulator {simulator_id} via simulator_ops")
                return

            logger.warning(f"Initial simulator stop failed for {simulator_id}, trying fallbacks. Error: {error}")

            # Second attempt: Try direct K8s deletion if available
            if hasattr(self.manager, 'k8s_client') and self.manager.k8s_client:
                try:
                    k8s_success = await self.manager.k8s_client.delete_simulator_deployment(simulator_id)
                    if k8s_success:
                        logger.info(f"Successfully stopped simulator {simulator_id} via direct K8s deletion")

                        # Update session metadata
                        await self.manager.store.session_store.update_session_metadata(session_id, {
                            'simulator_status': SimulatorStatus.STOPPED.value,
                            'simulator_id': None,
                            'simulator_endpoint': None
                        })

                        # Publish simulator stopped event
                        await event_bus.publish('simulator_stopped',
                                              session_id=session_id,
                                              simulator_id=simulator_id)
                        return
                except Exception as k8s_error:
                    logger.error(f"K8s fallback deletion failed for {simulator_id}: {k8s_error}")

            # Final fallback: Update metadata anyway to avoid future reconnection attempts
            await self.manager.store.session_store.update_session_metadata(session_id, {
                'simulator_status': SimulatorStatus.ERROR.value,
                'simulator_id': None,
                'simulator_endpoint': None,
                'simulator_error': "Failed to stop properly during pod shutdown"
            })

            # Publish simulator error event
            await event_bus.publish('simulator_error',
                                  session_id=session_id,
                                  simulator_id=simulator_id,
                                  error="Failed to stop properly during pod shutdown")

            logger.warning(f"All shutdown attempts failed for simulator {simulator_id}, marked as ERROR in metadata")

        except Exception as e:
            logger.error(f"Unexpected error stopping simulator {simulator_id} during shutdown: {e}", exc_info=True)

            # Publish error event
            await event_bus.publish('simulator_error',
                                  session_id=session_id,
                                  simulator_id=simulator_id,
                                  error=str(e))