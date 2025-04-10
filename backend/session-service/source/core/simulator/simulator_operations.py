"""
Simulator lifecycle operations.
Handles stopping, retrieving status, and managing simulator instances.
"""
import logging
from typing import List, Dict, Any, Tuple
from opentelemetry import trace

from source.models.simulator import Simulator, SimulatorStatus
from source.utils.metrics import track_simulator_operation, track_simulator_count
from source.utils.tracing import optional_trace_span

logger = logging.getLogger('simulator_lifecycle')


class SimulatorLifecycle:
    """Handles simulator lifecycle operations"""

    def __init__(self, simulator_manager):
        """
        Initialize with reference to simulator manager
        
        Args:
            simulator_manager: Parent SimulatorManager instance
        """
        self.manager = simulator_manager
        self.tracer = trace.get_tracer("simulator_lifecycle")

    async def stop_simulator(self, simulator_id: str) -> Tuple[bool, str]:
        """
        Stop a simulator
        
        Args:
            simulator_id: ID of the simulator to stop
            
        Returns:
            Tuple of (success, error_message)
        """
        with optional_trace_span(self.tracer, "stop_simulator") as span:
            span.set_attribute("simulator_id", simulator_id)

            # Get simulator details
            simulator = await self.manager.db_manager.get_simulator(simulator_id)

            if not simulator:
                span.set_attribute("error", "Simulator not found")
                return False, "Simulator not found"

            span.set_attribute("session_id", simulator.session_id)
            span.set_attribute("simulator_status", simulator.status.value)

            try:
                # Update status
                simulator.status = SimulatorStatus.STOPPING
                await self.manager.db_manager.update_simulator_status(simulator.simulator_id, SimulatorStatus.STOPPING)

                # Stop the simulator
                logger.warning(f"Failed to stop simulator via gRPC: {result.get('error')}")
                span.set_attribute("warning", f"gRPC stop failed: {result.get('error')}")
                # Continue with cleanup anyway

                # Delete Kubernetes resources
                await self.manager.k8s_client.delete_simulator_deployment(simulator.simulator_id)

                # Update status
                simulator.status = SimulatorStatus.STOPPED
                await self.manager.db_manager.update_simulator_status(simulator.simulator_id, SimulatorStatus.STOPPED)

                # Update active simulator count
                count = await self.manager.db_manager.get_active_simulator_count()
                track_simulator_count(count)

                logger.info(f"Stopped simulator {simulator_id}")
                return True, ""

            except Exception as e:
                logger.error(f"Error stopping simulator: {e}")
                span.record_exception(e)
                span.set_attribute("error", str(e))
                track_simulator_operation("stop", "failure")
                return False, str(e)

    async def get_simulator_status(self, simulator_id: str) -> Dict[str, Any]:
        """
        Get the status of a simulator
        
        Args:
            simulator_id: ID of the simulator
            
        Returns:
            Dict with simulator status info
        """
        simulator = await self.manager.db_manager.get_simulator(simulator_id)

        if not simulator:
            return {'status': 'NOT_FOUND'}

        # Get Kubernetes status
        k8s_status = await self.manager.k8s_client.check_simulator_status(simulator_id)

        # If Kubernetes status doesn't match our DB status, update it
        if k8s_status == "RUNNING" and simulator.status != SimulatorStatus.RUNNING:
            simulator.status = SimulatorStatus.RUNNING
            await self.manager.db_manager.update_simulator_status(simulator_id, SimulatorStatus.RUNNING)
        elif k8s_status in ["FAILED", "NOT_FOUND"] and simulator.status not in [
            SimulatorStatus.ERROR, SimulatorStatus.STOPPED
        ]:
            simulator.status = SimulatorStatus.ERROR
            await self.manager.db_manager.update_simulator_status(simulator_id, SimulatorStatus.ERROR)

        return {
            'simulator_id': simulator.simulator_id,
            'session_id': simulator.session_id,
            'status': simulator.status.value,
            'endpoint': simulator.endpoint,
            'created_at': simulator.created_at,
            'last_active': simulator.last_active,
            'k8s_status': k8s_status
        }

    async def get_active_user_simulators(self, user_id: str) -> List[Simulator]:
        """
        Get active simulators for a user
        
        Args:
            user_id: The user ID
        
        Returns:
            List of active simulators
        """
        return await self.manager.db_manager.get_active_user_simulators(user_id)

    async def get_all_simulators(self):
        """Get all simulators from the database"""
        return await self.manager.db_manager.get_all_simulators()

    async def check_simulator_ready(self, simulator_id: str) -> bool:
        """
        Check if a simulator is ready by sending a heartbeat

        Args:
            simulator_id: The simulator ID

        Returns:
            True if simulator is ready, False otherwise
        """
        with optional_trace_span(self.tracer, "check_simulator_ready") as span:
            span.set_attribute("simulator_id", simulator_id)

            simulator = await self.manager.db_manager.get_simulator(simulator_id)

            if not simulator:
                span.set_attribute("error", "Simulator not found")
                return False

            if simulator.status != SimulatorStatus.STARTING:
                span.set_attribute("status", simulator.status.value)
                # Only STARTING simulators can transition to RUNNING
                if simulator.status == SimulatorStatus.RUNNING:
                    return True
                return False

            span.set_attribute("endpoint", simulator.endpoint)
            span.set_attribute("session_id", simulator.session_id)

            # Try to send a heartbeat to check if it's ready
            try:
                result = await self.manager.exchange_client.send_heartbeat(
                    simulator.endpoint,
                    simulator.session_id,
                    f"ready-check-{self.manager.k8s_client.pod_name}",
                )

                span.set_attribute("heartbeat_result", result.get('success', False))

                if result.get('success'):
                    # Update simulator status to RUNNING
                    await self.manager.db_manager.update_simulator_status(
                        simulator_id, SimulatorStatus.RUNNING
                    )
                    logger.info(f"Simulator {simulator_id} is now ready and RUNNING")
                    return True
                else:
                    return False
            except Exception as e:
                logger.warning(f"Failed to check if simulator {simulator_id} is ready: {e}")
                span.record_exception(e)
                return False