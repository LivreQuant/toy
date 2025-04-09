"""
Simulator creation operations.
Handles creating new simulator instances including database and Kubernetes resources.
"""
import logging
import time
from typing import List, Optional, Tuple
from opentelemetry import trace

from source.models.simulator import Simulator, SimulatorStatus
from source.utils.metrics import track_simulator_creation_time, track_simulator_operation, track_simulator_count
from source.utils.tracing import optional_trace_span
from source.config import config

logger = logging.getLogger('simulator_creator')


class SimulatorCreator:
    """Handles simulator creation operations"""

    def __init__(self, simulator_manager):
        """
        Initialize with reference to simulator manager
        
        Args:
            simulator_manager: Parent SimulatorManager instance
        """
        self.manager = simulator_manager
        self.tracer = trace.get_tracer("simulator_creator")

    async def create_simulator(
            self,
            session_id: str,
            user_id: str,
    ) -> Tuple[Optional[Simulator], str]:
        """
        Create a new simulator instance
        
        Args:
            session_id: The session ID
            user_id: The user ID

        Returns:
            Tuple of (simulator, error_message)
        """
        with optional_trace_span(self.tracer, "create_simulator") as span:
            start_time = time.time()

            span.set_attribute("session_id", session_id)
            span.set_attribute("user_id", user_id)

            # Check user simulator limits
            existing_simulators = await self.manager.db_manager.get_active_user_simulators(user_id)

            span.set_attribute("existing_simulators_count", len(existing_simulators))

            if len(existing_simulators) >= self.manager.max_simulators_per_user:
                error_msg = f"Maximum simulator limit ({self.manager.max_simulators_per_user}) reached"
                span.set_attribute("error", error_msg)
                track_simulator_operation("create", "limit_exceeded")
                return None, error_msg

            # Check if there's an existing RUNNING simulator for this session
            existing_simulator = await self.manager.db_manager.get_simulator_by_session(session_id)
            if existing_simulator and existing_simulator.status == SimulatorStatus.RUNNING:
                logger.info(f"Returning existing active simulator for session {session_id}")
                span.set_attribute("simulator_id", existing_simulator.simulator_id)
                span.set_attribute("simulator_status", existing_simulator.status.value)
                span.set_attribute("reused_existing", True)
                track_simulator_operation("reuse_existing")
                return existing_simulator, ""
            
            # Create new simulator
            simulator = Simulator(
                session_id=session_id,
                user_id=user_id,
                status=SimulatorStatus.CREATING,
            )

            try:
                # Save to database
                await self.manager.db_manager.create_simulator(simulator)
                span.set_attribute("simulator_id", simulator.simulator_id)

                # Create Kubernetes deployment
                endpoint = await self.manager.k8s_client.create_simulator_deployment(
                    simulator.simulator_id,
                    session_id,
                    user_id,
                )

                # Update simulator with endpoint
                simulator.endpoint = endpoint
                simulator.status = SimulatorStatus.STARTING
                await self.manager.db_manager.update_simulator_endpoint(simulator.simulator_id, endpoint)
                await self.manager.db_manager.update_simulator_status(simulator.simulator_id, SimulatorStatus.STARTING)

                span.set_attribute("simulator_endpoint", endpoint)
                span.set_attribute("simulator_status", SimulatorStatus.STARTING.value)

                # Start the simulator via the exchange manager
                exchange_manager_endpoint = config.services.exchange_manager_service
                result = await self.manager.exchange_client.start_simulator(
                    exchange_manager_endpoint,
                    session_id,
                    user_id,
                )

                if not result.get('success'):
                    error_msg = result.get('error') or "Failed to start simulator"
                    logger.error(f"Failed to start simulator: {error_msg}")
                    span.set_attribute("error", error_msg)
                    simulator.status = SimulatorStatus.ERROR
                    await self.manager.db_manager.update_simulator_status(simulator.simulator_id, SimulatorStatus.ERROR)

                    # Clean up Kubernetes resources
                    await self.manager.k8s_client.delete_simulator_deployment(simulator.simulator_id)

                    return None, error_msg

                # Update simulator status
                simulator.status = SimulatorStatus.RUNNING
                await self.manager.db_manager.update_simulator_status(simulator.simulator_id, SimulatorStatus.RUNNING)

                span.set_attribute("simulator_status", SimulatorStatus.RUNNING.value)

                # Calculate creation time and track metrics
                creation_time = time.time() - start_time
                track_simulator_creation_time(creation_time)
                track_simulator_operation("create", "success")

                # Update active simulator count
                count = await self.manager.db_manager.get_active_simulator_count()
                track_simulator_count(count)

                logger.info(f"Created simulator {simulator.simulator_id} for session {session_id}")
                return simulator, ""

            except Exception as e:
                logger.error(f"Error creating simulator: {e}")
                span.record_exception(e)

                # Update simulator status
                if simulator:
                    simulator.status = SimulatorStatus.ERROR
                    await self.manager.db_manager.update_simulator_status(simulator.simulator_id, SimulatorStatus.ERROR)

                    # Clean up Kubernetes resources if needed
                    if hasattr(simulator, 'endpoint') and simulator.endpoint:
                        await self.manager.k8s_client.delete_simulator_deployment(simulator.simulator_id)

                track_simulator_operation("create", "error")
                return None, str(e)
