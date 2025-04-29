"""
Simulator manager for handling exchange simulator lifecycle.
Simplified for single-user mode with one simulator per session.
"""
import logging
import asyncio
import time
from typing import Optional, Tuple, Dict, Any, AsyncGenerator, Callable

from opentelemetry import trace

from source.utils.tracing import optional_trace_span
from source.utils.metrics import track_simulator_operation, track_simulator_count, track_simulator_creation_time
from source.utils.retry import retry_with_backoff_generator
from source.models.simulator import Simulator, SimulatorStatus

from source.models.exchange_data import ExchangeType
from source.core.exchange.factory import ExchangeAdapterFactory

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
        # Only store one callback to avoid duplication
        if self.data_callback:
            logger.warning("Overwriting existing data callback in simulator manager")

        self.data_callback = callback
        logger.debug("Data callback set for simulator manager")

    async def create_or_reuse_simulator(self, session_id: str, user_id: str) -> Tuple[Optional[Simulator], str]:
        """
        Create a simulator for the session or reuse an existing one.
        This is the main entry point for getting a simulator for a session.

        Args:
            session_id: Session ID
            user_id: User ID

        Returns:
            Tuple of (simulator, error_message)
        """
        with optional_trace_span(self.tracer, "create_or_reuse_simulator") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("user_id", user_id)

            # First try to find an existing simulator
            existing_simulator, error = await self.find_simulator(session_id, user_id)

            if existing_simulator:
                # Update our current simulator tracking
                self.current_simulator_id = existing_simulator.simulator_id
                self.current_endpoint = existing_simulator.endpoint

                # Update simulator session reference if it's from another session
                if existing_simulator.session_id != session_id:
                    logger.info(
                        f"Updating simulator {existing_simulator.simulator_id} to reference session {session_id}")

                    try:
                        # Update simulator in db to point to new session
                        await self.store_manager.simulator_store.update_simulator_session(
                            existing_simulator.simulator_id, session_id
                        )

                        # Update the simulator object's session_id
                        existing_simulator.session_id = session_id
                    except Exception as update_error:
                        logger.warning(f"Failed to update simulator session reference: {update_error}")
                        # Continue anyway - this is non-critical

                logger.info(f"Reusing existing simulator {existing_simulator.simulator_id}")
                return existing_simulator, ""

            # If no existing simulator was found, create a new one
            return await self.create_simulator(session_id, user_id)

    async def find_simulator(self, session_id: str, user_id: str) -> Tuple[Optional[Simulator], str]:
        """
        Find an existing simulator for the user.
        Handles checking both the current session and other sessions for this user.

        Args:
            session_id: Session ID
            user_id: User ID

        Returns:
            Tuple of (simulator, error_message)
        """
        with optional_trace_span(self.tracer, "find_simulator") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("user_id", user_id)

            # First check if we have a simulator in the current session
            existing_simulator = await self.store_manager.simulator_store.get_simulator_by_session(session_id)

            if existing_simulator and existing_simulator.status in [
                SimulatorStatus.RUNNING, SimulatorStatus.STARTING, SimulatorStatus.CREATING
            ]:
                logger.info(f"Found active simulator {existing_simulator.simulator_id} for session {session_id}")
                return existing_simulator, ""

            # If no simulator found for current session, look for any active simulator for this user
            if self.k8s_client:
                try:
                    user_simulators = await self.k8s_client.list_user_simulators(user_id)

                    # Find running simulators
                    running_simulators = [s for s in user_simulators if s.get('status') == 'RUNNING']

                    if running_simulators:
                        # Use the most recently created simulator
                        # Sort by created_at descending
                        running_simulators.sort(key=lambda x: x.get('created_at', 0), reverse=True)
                        simulator_data = running_simulators[0]
                        simulator_id = simulator_data.get('simulator_id')

                        # Get full simulator details from database
                        simulator = await self.store_manager.simulator_store.get_simulator(simulator_id)

                        if simulator:
                            logger.info(f"Found active simulator {simulator_id} for user {user_id}")
                            return simulator, ""
                except Exception as e:
                    error_msg = f"Error finding simulators for user {user_id}: {str(e)}"
                    logger.error(error_msg)
                    return None, error_msg

            return None, "No active simulator found"

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
        client_id: str,
        exchange_type: ExchangeType = None
    ):
        """
        Stream exchange data with retry mechanism and adapter support.

        Args:
            endpoint: The simulator endpoint
            session_id: The session ID
            client_id: The client ID
            exchange_type: Type of exchange to use adapter for

        Yields:
            Standardized ExchangeDataUpdate objects
        """
        if not self.exchange_client:
            logger.error("Exchange client not available")
            raise ValueError("Exchange client not available")

        # Use the specified exchange type or default to EQUITIES for existing simulator
        exchange_type = exchange_type or ExchangeType.EQUITIES

        # Update simulator status to RUNNING when streaming begins
        if self.current_simulator_id:
            try:
                await self.store_manager.simulator_store.update_simulator_status(
                    self.current_simulator_id, SimulatorStatus.RUNNING
                )
                logger.info(f"Simulator {self.current_simulator_id} now RUNNING")
            except Exception as e:
                logger.error(f"Error updating simulator status: {e}")
                # Continue despite the error - this is non-critical

        async def _stream_data():
            # Pass the exchange type to the exchange client
            async for standardized_data in self.exchange_client.stream_exchange_data(
                    endpoint, session_id, client_id, exchange_type
            ):
                # Generate a data ID safely without using .get()
                if hasattr(standardized_data, 'timestamp') and hasattr(standardized_data, 'update_id'):
                    data_id = f"{standardized_data.timestamp}-{standardized_data.update_id}"
                else:
                    data_id = f"{time.time()}-{uuid.uuid4()}"
                    
                logger.info(f"Received exchange data [ID: {data_id}] from simulator at {endpoint}")

                # Call the callback function if set - pass standardized data directly
                if self.data_callback:
                    try:
                        # Check if callback is a coroutine function and await it properly
                        if asyncio.iscoroutinefunction(self.data_callback):
                            await self.data_callback(standardized_data)
                        else:
                            self.data_callback(standardized_data)
                    except Exception as e:
                        logger.error(f"Error in data callback: {e}", exc_info=True)

                # Always yield the standardized data
                yield standardized_data

        # Use retry generator to handle connection issues
        try:
            async for data in retry_with_backoff_generator(
                    _stream_data,
                    max_attempts=5,
                    retriable_exceptions=(ConnectionError, TimeoutError)
            ):
                yield data
        except GeneratorExit:
            # Handle generator exit gracefully
            logger.info(f"Exchange data stream for {session_id} closed")
        except Exception as e:
            logger.error(f"Unhandled error in simulator data stream: {e}", exc_info=True)
            # Update status if possible
            if self.current_simulator_id:
                try:
                    await self.store_manager.simulator_store.update_simulator_status(
                        self.current_simulator_id, SimulatorStatus.ERROR
                    )
                except Exception:
                    pass  # Ignore errors when trying to update status during an error
            raise  # Re-raise to let caller handle

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

            logger.info(f"STOPPING SIMULATOR: {simulator_id} : {force}")

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

                logger.info(f"Calling Kubernetes client to delete simulator deployment {simulator_id}")
                try:
                    k8s_success = await self.k8s_client.delete_simulator_deployment(simulator_id)
                    logger.info(f"Kubernetes delete result: {k8s_success}")
                except Exception as k8s_error:
                    logger.error(f"Kubernetes delete error: {str(k8s_error)}", exc_info=True)
                    k8s_success = False

                # Update status to STOPPED
                await self.store_manager.simulator_store.update_simulator_status(simulator_id, SimulatorStatus.STOPPED)
                logger.info(f"Simulator {simulator_id} stopped")

                # Clear current simulator tracking
                if self.current_simulator_id == simulator_id:
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
