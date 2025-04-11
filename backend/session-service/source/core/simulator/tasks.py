"""
Simulator tasks.
Handles cleaning up inactive simulators and orphaned resources.
"""
import logging
import asyncio
import time
import random
from opentelemetry import trace

from source.utils.metrics import track_cleanup_operation

from source.models.simulator import SimulatorStatus

logger = logging.getLogger('simulator_cleanup')


class SimulatorTasks:
    """Handles simulator tasks"""

    def __init__(self, simulator_manager):
        """
        Initialize with reference to simulator manager
        
        Args:
            simulator_manager: Parent SimulatorManager instance
        """
        self.manager = simulator_manager
        self.tracer = trace.get_tracer("simulator_cleanup")

    async def cleanup_inactive_simulators(self):
        """Clean up simulators that have been inactive beyond the timeout"""
        # First, handle database cleanup
        count = await self.manager.db_manager.cleanup_inactive_simulators(self.manager.inactivity_timeout)

        if count > 0:
            logger.info(f"Marked {count} inactive simulators as STOPPED in database")

            # Get all active simulators
            active_simulators = await self.manager.db_manager.get_all_active_simulators()

            # Filter for those that exceeded timeout
            current_time = time.time()
            inactive_ids = [
                sim['simulator_id'] for sim in active_simulators
                if current_time - sim['last_active'] > self.manager.inactivity_timeout
                   and sim['status'] != SimulatorStatus.STOPPED.value
            ]

            # Clean up Kubernetes resources for each in parallel
            cleanup_tasks = []
            for simulator_id in inactive_ids:
                task = asyncio.create_task(
                    self._cleanup_simulator_resources(simulator_id)
                )
                cleanup_tasks.append(task)

            if cleanup_tasks:
                # Wait for all cleanup tasks with a timeout
                done, pending = await asyncio.wait(
                    cleanup_tasks,
                    timeout=30.0,  # 30 seconds max for cleanup
                    return_when=asyncio.ALL_COMPLETED
                )

                # Cancel any pending tasks
                for task in pending:
                    task.cancel()

                logger.info(f"Completed cleanup for {len(done)}/{len(cleanup_tasks)} inactive simulators")

        # Now check for inconsistencies between database and K8s
        try:
            # This is a more thorough check that happens less frequently
            if random.random() < 0.2:  # 20% chance to run on each cleanup cycle
                orphaned_count = await self._check_for_orphaned_simulators()
                if orphaned_count > 0:
                    logger.info(f"Cleaned up {orphaned_count} orphaned K8s simulator resources")
                    track_cleanup_operation("orphaned_simulators", orphaned_count)
        except Exception as e:
            logger.error(f"Error checking for orphaned simulators: {e}")

        return count

    async def _cleanup_simulator_resources(self, simulator_id):
        """Clean up resources for a specific simulator"""
        try:
            # Clean up Kubernetes resources
            await self.manager.k8s_client.delete_simulator_deployment(simulator_id)
            logger.info(f"Deleted Kubernetes resources for inactive simulator {simulator_id}")

            # Update simulator status in database to confirm cleanup
            await self.manager.db_manager.update_simulator_status(simulator_id, SimulatorStatus.STOPPED)
        except Exception as e:
            logger.error(f"Error cleaning up simulator {simulator_id}: {e}")

    async def _check_for_orphaned_simulators(self):
        """Check for simulators in K8s that aren't in our database"""
        try:
            # Get all K8s deployments for simulators
            k8s_simulators = await self.manager.k8s_client.list_simulator_deployments()

            # Get all simulators in database
            db_simulators = await self.manager.db_manager.get_all_simulators()
            db_simulator_ids = {sim.simulator_id for sim in db_simulators}

            # Find orphaned simulators in K8s
            deleted_count = 0
            for k8s_sim in k8s_simulators:
                simulator_id = k8s_sim.get('simulator_id')
                if simulator_id and simulator_id not in db_simulator_ids:
                    logger.warning(f"Found orphaned simulator in K8s: {simulator_id}")

                    # Delete orphaned deployment
                    await self.manager.k8s_client.delete_simulator_deployment(simulator_id)
                    logger.info(f"Deleted orphaned K8s simulator: {simulator_id}")
                    deleted_count += 1

            return deleted_count
        except Exception as e:
            logger.error(f"Error checking for orphaned simulators: {e}")
            return 0
