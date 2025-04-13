"""
Simulator manager for handling exchange simulator lifecycle.
Simplified for single-user mode with one simulator per session.
"""
import logging
import time
from typing import Optional, Tuple, Dict, Any, AsyncGenerator, Callable

from opentelemetry import trace

from source.utils.tracing import optional_trace_span
from source.utils.metrics import track_simulator_operation, track_simulator_count, track_simulator_creation_time
from source.utils.retry import retry_with_backoff_generator
from source.models.simulator import Simulator, SimulatorStatus

logger = logging.getLogger('simulator_manager')


class SimulatorManager:
    """Manager for a single exchange simulator instance"""

    def __init__(
        self,
        store_manager,
        exchange_client=None,
        k8s_client=None
    ):
        """
        Initialize simulator manager

        Args:
            store_manager: PostgreSQL store for simulator persistence
            exchange_client: Exchange client for communication with simulator
            k8s_client: Kubernetes client for simulator management
        """
        self.store_manager = store_manager
        self.exchange_client = exchange_client
        self.k8s_client = k8s_client

        # Track the current simulator
        self.current_simulator_id = None
        self.current_endpoint = None

        # Data callback for streaming data
        self.data_callback = None

        # Create tracer
        self.tracer = trace.get_tracer("simulator_manager")

        logger.info("Simulator manager initialized")

    def set_data_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        Set callback function to be called when exchange data is received

        Args:
            callback: Function that accepts exchange data dictionary
        """
        self.data_callback = callback
        logger.debug("Data callback set for simulator manager")

    async def create_simulator(self, session_id: str, user_id: str) -> Tuple[Optional[Simulator], str]:
        """
        Create a simulator for the session.
        For single-user mode, only one simulator can exist at a time.

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

            # If we already have a simulator running, return it
            if self.current_simulator_id:
                existing_simulator = await self.store_manager.simulator_store.get_simulator(self.current_simulator_id)
                if existing_simulator and existing_simulator.status in [
                    SimulatorStatus.RUNNING, SimulatorStatus.STARTING, SimulatorStatus.CREATING
                ]:
                    logger.info(f"Returning existing simulator {existing_simulator.simulator_id}")
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
                await self.store_manager.simulator_store.create_simulator(simulator)

                # Update our current simulator tracking
                self.current_simulator_id = simulator.simulator_id
                span.set_attribute("simulator_id", simulator.simulator_id)

                logger.info(f"Creating simulator {simulator.simulator_id} for session {session_id}")

                # Verify K8s client is available
                if not self.k8s_client:
                    logger.error("Kubernetes client not available")
                    await self.store_manager.simulator_store.update_simulator_status(
                        simulator.simulator_id, SimulatorStatus.ERROR)
                    return None, "Kubernetes client not available"

                # Create Kubernetes deployment
                endpoint = await self.k8s_client.create_simulator_deployment(
                    simulator.simulator_id,
                    session_id,
                    user_id
                )

                # Store the endpoint for future use
                self.current_endpoint = endpoint

                # Update simulator with endpoint and set to STARTING status
                simulator.endpoint = endpoint
                simulator.status = SimulatorStatus.STARTING
                await self.store_manager.simulator_store.update_simulator_endpoint(simulator.simulator_id, endpoint)
                await self.store_manager.simulator_store.update_simulator_status(simulator.simulator_id, SimulatorStatus.STARTING)

                # Calculate creation time and track metrics
                creation_time = time.time() - start_time
                track_simulator_creation_time(creation_time)
                track_simulator_operation("create", "success")
                track_simulator_count(1)

                logger.info(f"Created simulator {simulator.simulator_id} for session {session_id}")
                return simulator, ""

            except Exception as e:
                logger.error(f"Error creating simulator: {e}", exc_info=True)
                span.record_exception(e)
                self.current_simulator_id = None
                self.current_endpoint = None

                # Update status to ERROR if needed
                try:
                    await self.store_manager.simulator_store.update_simulator_status(
                        simulator.simulator_id, SimulatorStatus.ERROR)
                except Exception:
                    pass

                track_simulator_operation("create", "error")
                return None, f"Error creating simulator: {str(e)}"

    async def stream_exchange_data(
            self,
            endpoint: str,
            session_id: str,
            client_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream exchange data with retry mechanism.

        Args:
            endpoint: The simulator endpoint
            session_id: The session ID
            client_id: The client ID

        Yields:
            Dict with exchange data
        """
        if not self.exchange_client:
            logger.error("Exchange client not available")
            raise ValueError("Exchange client not available")

        # Update simulator status to RUNNING when streaming begins
        if self.current_simulator_id:
            await self.store_manager.simulator_store.update_simulator_status(
                self.current_simulator_id, SimulatorStatus.RUNNING
            )
            logger.info(f"Simulator {self.current_simulator_id} now RUNNING")

        async def _stream_data():
            async for data in self.exchange_client.stream_exchange_data(
                    endpoint, session_id, client_id
            ):
                # Call the callback function if set
                if self.data_callback:
                    try:
                        self.data_callback(data)
                    except Exception as e:
                        logger.error(f"Error in data callback: {e}")

                # Always yield the data regardless of callback
                yield data

        # Use retry generator to handle connection issues
        async for data in retry_with_backoff_generator(
                _stream_data,
                max_attempts=5,
                retriable_exceptions=(ConnectionError, TimeoutError)
        ):
            yield data

    async def stop_simulator(self, simulator_id: str = None, force: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Stop the current simulator

        Args:
            simulator_id: Optional simulator ID (defaults to current)
            force: Force stop even if in terminal state

        Returns:
            Tuple of (success, error_message)
        """
        with optional_trace_span(self.tracer, "stop_simulator") as span:
            # Use current simulator ID if none provided
            simulator_id = simulator_id or self.current_simulator_id
            if not simulator_id:
                return True, "No simulator to stop"

            span.set_attribute("simulator_id", simulator_id)
            span.set_attribute("force", force)

            # Get simulator details from database
            simulator = await self.store_manager.simulator_store.get_simulator(simulator_id)
            if not simulator:
                # Clear current simulator tracking
                self.current_simulator_id = None
                self.current_endpoint = None
                return False, "Simulator not found"

            session_id = simulator.session_id
            span.set_attribute("session_id", session_id)

            # Check if already stopped
            if simulator.status == SimulatorStatus.STOPPED and not force:
                # Already stopped, clear tracking
                self.current_simulator_id = None
                self.current_endpoint = None
                return True, ""

            try:
                # Update status to STOPPING
                await self.store_manager.simulator_store.update_simulator_status(simulator_id, SimulatorStatus.STOPPING)
                logger.info(f"Stopping simulator {simulator_id}")

                # Delete Kubernetes resources
                if not self.k8s_client:
                    logger.error("Kubernetes client not available")
                    return False, "Kubernetes client not available"

                k8s_success = await self.k8s_client.delete_simulator_deployment(simulator_id)

                # Update status to STOPPED
                await self.store_manager.simulator_store.update_simulator_status(simulator_id, SimulatorStatus.STOPPED)
                logger.info(f"Simulator {simulator_id} stopped")

                # Clear current simulator tracking
                self.current_simulator_id = None
                self.current_endpoint = None

                track_simulator_operation("stop", "success" if k8s_success else "partial")
                track_simulator_count(0)

                return k8s_success, "" if k8s_success else "Failed to delete Kubernetes resources"

            except Exception as e:
                logger.error(f"Error stopping simulator: {e}", exc_info=True)
                span.record_exception(e)

                # Only clear tracking on successful stop
                if force:
                    self.current_simulator_id = None
                    self.current_endpoint = None

                track_simulator_operation("stop", "failure")
                return False, f"Error stopping simulator: {str(e)}"
