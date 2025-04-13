"""
Simulator manager for handling exchange simulator lifecycle.
Simplified for singleton mode with one simulator per session.
"""
import logging
import time
from typing import Optional, Tuple

from opentelemetry import trace

from source.utils.event_bus import event_bus
from source.utils.tracing import optional_trace_span
from source.utils.metrics import track_simulator_operation, track_simulator_count, track_simulator_creation_time
from source.models.simulator import Simulator, SimulatorStatus

logger = logging.getLogger('simulator_manager')


class SimulatorManager:
    """Manager for exchange simulator instances"""

    def __init__(
        self,
        store_manager,
        k8s_client=None
    ):
        """
        Initialize simulator manager
        
        Args:
            store_manager: PostgreSQL store for simulator persistence
            k8s_client: Kubernetes client for simulator management
        """
        self.store_manager = store_manager
        self.k8s_client = k8s_client
        
        # Create tracer
        self.tracer = trace.get_tracer("simulator_manager")

        logger.info("Simulator manager initialized")
    
    # ----- Public API methods -----

    async def create_simulator(self, session_id: str, user_id: str) -> Tuple[Optional[Simulator], str]:
        """
        Create a new simulator for a session

        Args:
            session_id: Session ID
            user_id: User ID

        Returns:
            Tuple of (simulator, error_message)
        """
        with optional_trace_span(self.tracer, "create_simulator") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("user_id", user_id)
            start_time = time.time()

            # Check if there's an existing simulator for this session
            existing_simulator = await self.store_manager.simulator_store.get_simulator_by_session(session_id)
            if existing_simulator and existing_simulator.status in [
                SimulatorStatus.RUNNING, SimulatorStatus.STARTING, SimulatorStatus.CREATING
            ]:
                logger.info(f"Returning existing simulator {existing_simulator.simulator_id} for session {session_id}")
                track_simulator_operation("reuse_existing")

                # Publish existing simulator reuse event
                await event_bus.publish('simulator_reused',
                                        session_id=session_id,
                                        simulator_id=existing_simulator.simulator_id)

                return existing_simulator, ""

            # Create new simulator
            simulator = Simulator(
                session_id=session_id,
                user_id=user_id,
                status=SimulatorStatus.CREATING
            )

            try:
                # Save to database
                await self.store_manager.simulator_store.create_simulator(simulator)
                span.set_attribute("simulator_id", simulator.simulator_id)

                # Publish simulator creation event
                await event_bus.publish('simulator_creating',
                                        session_id=session_id,
                                        simulator_id=simulator.simulator_id,
                                        user_id=user_id)

                # Verify K8s client is available
                if not self.k8s_client:
                    logger.error("Kubernetes client not available")
                    await self.store_manager.simulator_store.update_simulator_status(
                        simulator.simulator_id, SimulatorStatus.ERROR)

                    # Publish error event
                    await event_bus.publish('simulator_error',
                                            session_id=session_id,
                                            simulator_id=simulator.simulator_id,
                                            error="Kubernetes client not available")

                    return None, "Kubernetes client not available"

                # Create Kubernetes deployment
                endpoint = await self.k8s_client.create_simulator_deployment(
                    simulator.simulator_id,
                    session_id,
                    user_id
                )

                # Update simulator with endpoint and set to STARTING status
                simulator.endpoint = endpoint
                simulator.status = SimulatorStatus.STARTING
                await self.store_manager.simulator_store.update_simulator_endpoint(simulator.simulator_id, endpoint)
                await self.store_manager.simulator_store.update_simulator_status(simulator.simulator_id, SimulatorStatus.STARTING)

                # Calculate creation time and track metrics
                creation_time = time.time() - start_time
                track_simulator_creation_time(creation_time)
                track_simulator_operation("create", "success")
                track_simulator_count(1)  # In singleton mode, we have 0 or 1 simulators

                # Publish simulator starting event
                await event_bus.publish('simulator_starting',
                                        session_id=session_id,
                                        simulator_id=simulator.simulator_id,
                                        endpoint=endpoint)

                logger.info(f"Created simulator {simulator.simulator_id} for session {session_id}")
                return simulator, ""

            except Exception as e:
                logger.error(f"Error creating simulator: {e}", exc_info=True)
                span.record_exception(e)

                # Update simulator status to ERROR
                try:
                    await self.store_manager.simulator_store.update_simulator_status(
                        simulator.simulator_id, SimulatorStatus.ERROR)
                except Exception as update_error:
                    logger.error(f"Failed to update simulator status to ERROR: {update_error}")

                # Publish error event
                await event_bus.publish('simulator_error',
                                        session_id=session_id,
                                        simulator_id=simulator.simulator_id,
                                        error=str(e))

                track_simulator_operation("create", "error")
                return None, f"Error creating simulator: {str(e)}"

    async def stop_simulator(self, simulator_id: str) -> Tuple[bool, str]:
        """
        Stop a simulator by ID

        Args:
            simulator_id: Simulator ID

        Returns:
            Tuple of (success, error_message)
        """
        with optional_trace_span(self.tracer, "stop_simulator") as span:
            span.set_attribute("simulator_id", simulator_id)

            # Get simulator details
            simulator = await self.store_manager.simulator_store.get_simulator(simulator_id)
            if not simulator:
                return False, "Simulator not found"

            session_id = simulator.session_id
            span.set_attribute("session_id", session_id)

            # Check if already stopped
            if simulator.status == SimulatorStatus.STOPPED:
                # Already stopped, nothing to do
                await event_bus.publish('simulator_already_stopped',
                                        simulator_id=simulator_id,
                                        session_id=session_id)
                return True, ""

            try:
                # Update status to STOPPING
                await self.store_manager.simulator_store.update_simulator_status(simulator_id, SimulatorStatus.STOPPING)

                # Publish stopping event
                await event_bus.publish('simulator_stopping',
                                        simulator_id=simulator_id,
                                        session_id=session_id)

                # Delete Kubernetes resources
                if not self.k8s_client:
                    logger.error("Kubernetes client not available")
                    await self.store_manager.simulator_store.update_simulator_status(simulator_id, SimulatorStatus.ERROR)

                    # Publish error event
                    await event_bus.publish('simulator_error',
                                            simulator_id=simulator_id,
                                            session_id=session_id,
                                            error="Kubernetes client not available")

                    return False, "Kubernetes client not available"

                k8s_success = await self.k8s_client.delete_simulator_deployment(simulator_id)

                # Update status to STOPPED
                await self.store_manager.simulator_store.update_simulator_status(simulator_id, SimulatorStatus.STOPPED)

                # Publish stopped event
                await event_bus.publish('simulator_stopped',
                                        simulator_id=simulator_id,
                                        session_id=session_id,
                                        success=k8s_success)

                track_simulator_operation("stop", "success" if k8s_success else "partial")
                track_simulator_count(0)  # After stopping, we have 0 simulators

                if not k8s_success:
                    return False, "Failed to delete Kubernetes resources"

                return True, ""

            except Exception as e:
                logger.error(f"Error stopping simulator: {e}", exc_info=True)
                span.record_exception(e)

                # Try to update status to ERROR
                try:
                    await self.store_manager.simulator_store.update_simulator_status(simulator_id, SimulatorStatus.ERROR)

                    # Publish error event
                    await event_bus.publish('simulator_error',
                                            simulator_id=simulator_id,
                                            session_id=session_id,
                                            error=str(e))
                except Exception:
                    pass

                track_simulator_operation("stop", "failure")
                return False, f"Error stopping simulator: {str(e)}"

    async def check_simulator_ready(self, simulator_id: str) -> bool:
        """
        Check if a simulator in STARTING state is now ready
        
        Args:
            simulator_id: Simulator ID to check
            
        Returns:
            True if simulator is ready, False otherwise
        """
        try:
            # First check K8s status
            if self.k8s_client:
                status = await self.k8s_client.check_simulator_status(simulator_id)
                
                if status == "RUNNING":
                    # Update simulator status in database
                    await self.store_manager.simulator_store.update_simulator_status(
                        simulator_id, SimulatorStatus.RUNNING
                    )
                    return True
                    
                elif status in ["FAILED", "ERROR"]:
                    # Mark as error in database
                    await self.store_manager.simulator_store.update_simulator_status(
                        simulator_id, SimulatorStatus.ERROR
                    )
                    return False
            
            # Default to not ready
            return False
        except Exception as e:
            logger.error(f"Error checking simulator {simulator_id} readiness: {e}")
            return False
