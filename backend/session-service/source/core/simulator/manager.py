"""
Simulator manager for handling exchange simulator lifecycle.
Coordinates the creation, monitoring, and termination of simulator instances.
"""
import logging
import asyncio
import time
from typing import Optional, Tuple

from opentelemetry import trace

from source.config import config
from source.utils.tracing import optional_trace_span
from source.utils.metrics import track_simulator_operation, track_simulator_count, track_simulator_creation_time
from source.models.simulator import Simulator, SimulatorStatus

logger = logging.getLogger('simulator_manager')


class SimulatorManager:
    """Manager for exchange simulator instances"""

    def __init__(
        self,
        postgres_store,
        exchange_client=None,
        k8s_client=None
    ):
        """
        Initialize simulator manager
        
        Args:
            postgres_store: PostgreSQL store for simulator persistence
            redis_pubsub: Redis pub/sub for events
            exchange_client: Exchange client for gRPC communication
            k8s_client: Kubernetes client for simulator management
        """
        self.postgres_store = postgres_store
        self.exchange_client = exchange_client
        self.k8s_client = k8s_client
        
        # Configuration
        self.max_simulators_per_user = config.simulator.max_per_user
        self.inactivity_timeout = config.simulator.inactivity_timeout
        
        # Background tasks
        self.cleanup_task = None
        
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

            # Check user simulator limits
            existing_simulators = await self.postgres_store.get_active_user_simulators(user_id)
            span.set_attribute("existing_simulators_count", len(existing_simulators))

            if len(existing_simulators) >= self.max_simulators_per_user:
                error_msg = f"Maximum simulator limit ({self.max_simulators_per_user}) reached"
                span.set_attribute("error", error_msg)
                track_simulator_operation("create", "limit_exceeded")
                return None, error_msg

            # Check if there's an existing simulator for this session
            existing_simulator = await self.postgres_store.get_simulator_by_session(session_id)
            if existing_simulator and existing_simulator.status in [
                SimulatorStatus.RUNNING, SimulatorStatus.STARTING, SimulatorStatus.CREATING
            ]:
                logger.info(f"Returning existing simulator {existing_simulator.simulator_id} for session {session_id}")
                track_simulator_operation("reuse_existing")
                return existing_simulator, ""

            # Create new simulator
            simulator = Simulator(
                session_id=session_id,
                user_id=user_id,
                status=SimulatorStatus.CREATING
            )

            try:
                # Save to database
                await self.postgres_store.create_simulator(simulator)
                span.set_attribute("simulator_id", simulator.simulator_id)

                # Verify K8s client is available
                if not self.k8s_client:
                    logger.error("Kubernetes client not available")
                    await self.postgres_store.update_simulator_status(
                        simulator.simulator_id, SimulatorStatus.ERROR)
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
                await self.postgres_store.update_simulator_endpoint(simulator.simulator_id, endpoint)
                await self.postgres_store.update_simulator_status(simulator.simulator_id, SimulatorStatus.STARTING)

                # Calculate creation time and track metrics
                creation_time = time.time() - start_time
                track_simulator_creation_time(creation_time)
                track_simulator_operation("create", "success")
                track_simulator_count(await self.postgres_store.get_active_simulator_count())

                # Publish event
                if self.redis_pubsub:
                    try:
                        await self.redis_pubsub.publish_event('simulator_created', {
                            'session_id': session_id,
                            'simulator_id': simulator.simulator_id,
                            'user_id': user_id,
                            'status': SimulatorStatus.STARTING.value,
                            'endpoint': endpoint
                        })
                    except Exception as e:
                        logger.error(f"Failed to publish simulator creation event: {e}")

                logger.info(f"Created simulator {simulator.simulator_id} for session {session_id}")
                return simulator, ""

            except Exception as e:
                logger.error(f"Error creating simulator: {e}", exc_info=True)
                span.record_exception(e)
                
                # Update simulator status to ERROR
                try:
                    await self.postgres_store.update_simulator_status(
                        simulator.simulator_id, SimulatorStatus.ERROR)
                except Exception as update_error:
                    logger.error(f"Failed to update simulator status to ERROR: {update_error}")
                
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
            simulator = await self.postgres_store.get_simulator(simulator_id)
            if not simulator:
                return False, "Simulator not found"

            # Check if already stopped
            if simulator.status == SimulatorStatus.STOPPED:
                return True, ""

            try:
                # Update status to STOPPING
                await self.postgres_store.update_simulator_status(simulator_id, SimulatorStatus.STOPPING)

                # Delete Kubernetes resources
                if not self.k8s_client:
                    logger.error("Kubernetes client not available")
                    await self.postgres_store.update_simulator_status(simulator_id, SimulatorStatus.ERROR)
                    return False, "Kubernetes client not available"

                k8s_success = await self.k8s_client.delete_simulator_deployment(simulator_id)
                
                # Update status to STOPPED
                await self.postgres_store.update_simulator_status(simulator_id, SimulatorStatus.STOPPED)

                # Publish event
                if self.redis_pubsub:
                    try:
                        await self.redis_pubsub.publish_event('simulator_stopped', {
                            'simulator_id': simulator_id,
                            'session_id': simulator.session_id,
                            'user_id': simulator.user_id
                        })
                    except Exception as e:
                        logger.error(f"Failed to publish simulator stopped event: {e}")

                track_simulator_operation("stop", "success" if k8s_success else "partial")
                
                if not k8s_success:
                    return False, "Failed to delete Kubernetes resources"
                    
                return True, ""

            except Exception as e:
                logger.error(f"Error stopping simulator: {e}", exc_info=True)
                span.record_exception(e)
                
                # Try to update status to STOPPED anyway
                try:
                    await self.postgres_store.update_simulator_status(simulator_id, SimulatorStatus.STOPPED)
                except Exception:
                    pass
                    
                track_simulator_operation("stop", "failure")
                return False, f"Error stopping simulator: {str(e)}"

    # ----- Background tasks -----
    
    async def start_cleanup_task(self):
        """Start background cleanup task"""
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._run_cleanup_loop())
            logger.info("Started simulator cleanup task")
    
    async def stop_cleanup_task(self):
        """Stop background cleanup task"""
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                logger.info("Simulator cleanup task cancelled")
            except Exception as e:
                logger.error(f"Error awaiting cancelled cleanup task: {e}")
            self.cleanup_task = None
            logger.info("Simulator cleanup task stopped")
            
    async def _run_cleanup_loop(self):
        """Background loop for cleanup tasks"""
        logger.info("Simulator cleanup loop starting")
        while True:
            try:
                await self._cleanup_inactive_simulators()
                await asyncio.sleep(300)  # Run every 5 minutes
            except asyncio.CancelledError:
                logger.info("Simulator cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in simulator cleanup loop: {e}", exc_info=True)
                await asyncio.sleep(60)
                
    async def _cleanup_inactive_simulators(self):
        """Clean up simulators that have been inactive beyond the timeout"""
        # Implementation details...
        pass
