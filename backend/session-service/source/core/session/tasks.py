"""
Background cleanup tasks for the session service.
Handles cleanup of expired sessions, inactive simulators, and heartbeat functions.
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
        """Check simulators in STARTING state and verify if they're ready"""
        try:
            # Use simulator manager to get starting simulators
            starting_simulators = await self.manager.simulator_manager.get_simulators_with_status(
                SimulatorStatus.STARTING)

            if not starting_simulators:
                return

            logger.debug(f"Checking {len(starting_simulators)} simulators in STARTING state")

            for simulator in starting_simulators:
                # Skip simulators that have been in STARTING state for too short a time
                if time.time() - simulator.last_active < 10:
                    continue

                # Check if simulator is ready
                is_ready = await self.manager.simulator_manager.check_simulator_ready(simulator.simulator_id)

                if is_ready:
                    logger.info(f"Simulator {simulator.simulator_id} is now RUNNING")

                    # Update session metadata
                    try:
                        await self.manager.update_session_metadata(simulator.session_id, {
                            'simulator_status': SimulatorStatus.RUNNING.value
                        })

                        # Publish simulator ready event
                        await event_bus.publish('simulator_ready',
                                                session_id=simulator.session_id,
                                                simulator_id=simulator.simulator_id,
                                                endpoint=simulator.endpoint)

                    except Exception as e:
                        logger.error(
                            f"Failed to update session metadata for simulator {simulator.simulator_id}: {e}")

        except Exception as e:
            logger.error(f"Error checking starting simulators: {e}", exc_info=True)

    async def run_cleanup_loop(self):
        """Background loop for periodic cleanup tasks"""
        logger.info("Session cleanup loop starting.")
        while True:
            try:
                logger.info("Running periodic cleanup...")
                # Cleanup expired sessions
                expired_count = await self.manager.store_manager.session_store.cleanup_expired_sessions()
                if expired_count > 0:
                    logger.info(f"Cleaned up {expired_count} expired sessions from DB.")
                    track_cleanup_operation("expired_sessions", expired_count)

                    # Publish cleanup event
                    await event_bus.publish('sessions_cleaned_up',
                                            count=expired_count,
                                            reason="expired")

                # Cleanup inactive simulators
                if self.manager.simulator_manager:
                    try:
                        inactive_sim_count = await self.manager.simulator_manager.cleanup_inactive_simulators()
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

                # Update active session/simulator count metrics
                active_sessions = await self.manager.store_manager.session_store.get_active_session_count()
                track_session_count(active_sessions, self.manager.pod_name)

                if self.manager.simulator_manager:
                    active_sims = await self.manager.simulator_manager.get_active_simulator_count()
                    track_simulator_count(active_sims, self.manager.pod_name)

                logger.info("Periodic cleanup finished.")
                # Sleep until next cleanup cycle
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
            heartbeat_missing_threshold = time.time() - (config.websocket.heartbeat_interval * 10)
            connection_missing_threshold = time.time() - 3600

            # Get potentially active sessions
            potentially_active_sessions = await self.manager.store_manager.session_store.get_sessions_with_criteria({
                'status': 'ACTIVE'
            })

            if not potentially_active_sessions:
                logger.debug("No active sessions found to check for zombies.")
                return 0

            for session in potentially_active_sessions:
                # Skip recently active sessions
                if session.last_active > heartbeat_missing_threshold:
                    continue

                # Check metadata for connection times
                metadata = session.metadata
                last_ws_connection = getattr(metadata, 'last_ws_connection', 0.0)
                last_sse_connection = getattr(metadata, 'last_sse_connection', 0.0)

                # If there was a recent connection, skip
                if max(last_ws_connection, last_sse_connection) > connection_missing_threshold:
                    continue

                # Skip very new sessions
                if time.time() - session.created_at < 300:
                    continue

                # This session is a zombie
                logger.info(f"Identified zombie session {session.session_id} (User: {session.user_id})")

                # Publish zombie session detected event
                await event_bus.publish('zombie_session_detected',
                                        session_id=session.session_id,
                                        user_id=session.user_id)

                # Stop associated simulator
                sim_id = getattr(metadata, 'simulator_id', None)
                sim_status = getattr(metadata, 'simulator_status', SimulatorStatus.NONE)
                if sim_id and sim_status != SimulatorStatus.STOPPED:
                    logger.info(f"Stopping simulator {sim_id} for zombie session {session.session_id}")
                    try:
                        await self.manager.stop_simulator(session.session_id, force=True)
                    except Exception as e:
                        logger.error(f"Error stopping simulator {sim_id} for zombie session: {e}", exc_info=True)

                # Mark session as expired
                logger.info(f"Marking zombie session {session.session_id} as EXPIRED.")
                await self.manager.store_manager.session_store.update_session_status(session.session_id, 'EXPIRED')

                # Publish session expired event
                await event_bus.publish('session_expired',
                                        session_id=session.session_id,
                                        reason="zombie")

                zombie_count += 1

        except Exception as e:
            logger.error(f"Error during zombie session cleanup: {e}", exc_info=True)

        if zombie_count > 0:
            logger.info(f"Finished cleaning up {zombie_count} zombie sessions.")
        else:
            logger.debug("No zombie sessions found needing cleanup.")

        return zombie_count

    async def cleanup_pod_sessions(self, pod_name):
        """Clean up sessions and simulators associated with this pod before shutdown"""
        logger.info("Starting cleanup of sessions managed by this pod.")
        try:
            # Get sessions for this pod
            pod_sessions = await self.manager.store_manager.session_store.get_sessions_with_criteria({
                'pod_name': pod_name
            })

            if not pod_sessions:
                logger.info("No active sessions found for this pod to clean up.")
                return

            logger.info(f"Found {len(pod_sessions)} sessions potentially managed by this pod. Initiating cleanup...")

            simulator_tasks = []
            sessions_to_update = []

            for session_data in pod_sessions:
                metadata = session_data.metadata
                session_id = session_data.session_id

                if not session_id:
                    continue

                simulator_id = getattr(metadata, 'simulator_id', None)
                simulator_status = getattr(metadata, 'simulator_status', None)
                simulator_endpoint = getattr(metadata, 'simulator_endpoint', None)

                sessions_to_update.append(session_id)

                # Check if session has a running simulator
                if simulator_id and simulator_status not in [SimulatorStatus.STOPPED.value, SimulatorStatus.ERROR.value,
                                                             None]:
                    logger.info(f"Scheduling simulator {simulator_id} for session {session_id} for shutdown.")
                    task = asyncio.create_task(
                        self.manager.simulator_ops.stop_simulator(
                            session_id,
                            force=True
                        )
                    )
                    simulator_tasks.append(task)
                else:
                    logger.debug(f"No active simulator found for session {session_id} to stop.")

            # Wait for simulator shutdowns with timeout
            if simulator_tasks:
                logger.info(f"Waiting for {len(simulator_tasks)} simulator shutdown tasks...")
                done, pending = await asyncio.wait(
                    simulator_tasks,
                    timeout=config.server.shutdown_timeout - 2.0,
                    return_when=asyncio.ALL_COMPLETED
                )

                logger.info(f"Completed {len(done)} simulator shutdown tasks.")
                if pending:
                    logger.warning(f"{len(pending)} simulator shutdown tasks timed out or were cancelled.")
                    for task in pending:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                        except Exception as e:
                            logger.error(f"Error awaiting cancelled simulator task: {e}", exc_info=True)

            # Update session metadata
            logger.info(f"Updating metadata for {len(sessions_to_update)} sessions to mark pod termination.")
            update_metadata = {
                'pod_terminating': True,
                'termination_time': time.time(),
                'simulator_status': SimulatorStatus.STOPPED.value
            }

            for s_id in sessions_to_update:
                try:
                    await self.manager.update_session_metadata(s_id, update_metadata)
                    await event_bus.publish('pod_terminating',
                                            session_id=s_id,
                                            pod_name=pod_name)
                except Exception as e:
                    logger.error(f"Error updating session {s_id} metadata during shutdown: {e}", exc_info=True)

            logger.info("Session cleanup phase complete.")

        except Exception as e:
            logger.error(f"Error during pod sessions cleanup: {e}", exc_info=True)
