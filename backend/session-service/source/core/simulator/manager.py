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
        Enhanced with health validation and single-simulator enforcement.

        Args:
            session_id: Session ID
            user_id: User ID

        Returns:
            Tuple of (simulator, error_message)
        """
        with optional_trace_span(self.tracer, "create_or_reuse_simulator") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("user_id", user_id)

            # First try to find and validate existing simulators
            existing_simulator, error = await self.find_and_validate_simulator(session_id, user_id)

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

                logger.info(f"Reusing validated healthy simulator {existing_simulator.simulator_id}")
                return existing_simulator, ""

            # If no existing healthy simulator was found, create a new one
            return await self.create_simulator(session_id, user_id)

    async def find_simulator(self, session_id: str, user_id: str) -> Tuple[Optional[Simulator], str]:
        """
        Find an existing simulator for the user (updated to be user-centric, not session-centric)
        """
        with optional_trace_span(self.tracer, "find_simulator") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("user_id", user_id)

            logger.info(f"Looking for existing simulators for user {user_id}")

            # Look for ANY active simulator for this user (not just current session)
            try:
                pool = await self.store_manager.simulator_store._get_pool()
                async with pool.acquire() as conn:
                    row = await conn.fetchrow('''
                        SELECT * FROM simulator.instances
                        WHERE user_id = $1 
                        AND status IN ('RUNNING', 'STARTING', 'CREATING')
                        ORDER BY created_at DESC
                        LIMIT 1
                    ''', user_id)

                    if row:
                        simulator = self.store_manager.simulator_store._row_to_entity(row)
                        if simulator:
                            logger.info(f"Found existing simulator {simulator.simulator_id} for user {user_id}")
                            return simulator, ""

                # Fallback to Kubernetes check
                if self.k8s_client:
                    try:
                        user_simulators = await self.k8s_client.list_user_simulators(user_id)
                        running_simulators = [s for s in user_simulators if s.get('status') == 'RUNNING']
                        
                        if running_simulators:
                            running_simulators.sort(key=lambda x: x.get('created_at', 0), reverse=True)
                            simulator_data = running_simulators[0]
                            simulator_id = simulator_data.get('simulator_id')
                            
                            simulator = await self.store_manager.simulator_store.get_simulator(simulator_id)
                            if simulator:
                                logger.info(f"Found K8s simulator {simulator_id} for user {user_id}")
                                return simulator, ""
                    except Exception as e:
                        logger.error(f"Error checking K8s simulators: {e}")

                return None, "No active simulator found"

            except Exception as e:
                logger.error(f"Error finding simulator: {e}", exc_info=True)
                return None, f"Database error: {str(e)}"

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
                await self.store_manager.simulator_store.create_simulator(simulator, user_id)

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
        """Stream exchange data with proper error handling for pod termination"""
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

        async def _stream_data():
            try:
                # Pass the exchange type to the exchange client
                async for standardized_data in self.exchange_client.stream_exchange_data(
                        endpoint, session_id, client_id, exchange_type
                ):
                    # Generate a data ID safely
                    if hasattr(standardized_data, 'timestamp') and hasattr(standardized_data, 'update_id'):
                        data_id = f"{standardized_data.timestamp}-{standardized_data.update_id}"
                    else:
                        data_id = f"{time.time()}-{id(standardized_data)}"
                        
                    logger.info(f"Received exchange data [ID: {data_id}] from simulator at {endpoint}")

                    # Call the callback function if set
                    if self.data_callback:
                        try:
                            if asyncio.iscoroutinefunction(self.data_callback):
                                await self.data_callback(standardized_data)
                            else:
                                self.data_callback(standardized_data)
                        except Exception as e:
                            logger.error(f"Error in data callback: {e}", exc_info=True)

                    yield standardized_data
            except Exception as e:
                logger.error(f"Stream data error: {e}")
                # ✅ ADD: Clean up simulator state on stream failure
                await self._handle_stream_failure(e)
                raise

        # ✅ IMPROVED: Better error handling with cleanup
        try:
            async for data in retry_with_backoff_generator(
                    _stream_data,
                    max_attempts=3,  # Reduce attempts for faster failure detection
                    retriable_exceptions=(ConnectionError, TimeoutError)  # Don't retry gRPC UNAVAILABLE
            ):
                yield data
        except GeneratorExit:
            logger.info(f"Exchange data stream for {session_id} closed gracefully")
            await self._handle_stream_closure()
        except Exception as e:
            logger.error(f"Unhandled error in simulator data stream: {e}", exc_info=True)
            await self._handle_stream_failure(e)
            raise

    async def _handle_stream_failure(self, error):
        """Handle stream failure - clean up state and update database"""
        logger.info(f"Handling stream failure for simulator {self.current_simulator_id}: {error}")
        
        if self.current_simulator_id:
            try:
                # Update database status to ERROR
                await self.store_manager.simulator_store.update_simulator_status(
                    self.current_simulator_id, SimulatorStatus.ERROR
                )
                logger.info(f"Updated simulator {self.current_simulator_id} status to ERROR in database")
            except Exception as db_error:
                logger.error(f"Failed to update simulator status in database: {db_error}")
            
            # Clear local tracking
            old_simulator_id = self.current_simulator_id
            self.current_simulator_id = None
            self.current_endpoint = None
            logger.info(f"Cleared local tracking for failed simulator {old_simulator_id}")

    async def _handle_stream_closure(self):
        """Handle graceful stream closure"""
        logger.info(f"Handling graceful stream closure for simulator {self.current_simulator_id}")
        # Don't update status to ERROR for graceful closure, just clear tracking
        if self.current_simulator_id:
            self.current_simulator_id = None
            self.current_endpoint = None
            
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
    
    async def validate_simulator_health(self, simulator_id: str = None) -> Tuple[bool, str]:
        """
        Validate that the current simulator is actually healthy and reachable
        
        Args:
            simulator_id: Optional simulator ID (defaults to current)
            
        Returns:
            Tuple of (is_healthy, error_message)
        """
        with optional_trace_span(self.tracer, "validate_simulator_health") as span:
            # Use current simulator ID if none provided
            simulator_id = simulator_id or self.current_simulator_id
            if not simulator_id:
                return True, "No simulator to validate"

            span.set_attribute("simulator_id", simulator_id)

            try:
                # Get simulator details from database
                simulator = await self.store_manager.simulator_store.get_simulator(simulator_id)
                if not simulator:
                    return False, "Simulator not found in database"

                # Check if status is actually RUNNING or STARTING
                if simulator.status not in [SimulatorStatus.RUNNING, SimulatorStatus.STARTING]:
                    return False, f"Simulator status is {simulator.status.value}, not active"

                # Check if we can connect to the endpoint
                if not simulator.endpoint:
                    return False, "Simulator has no endpoint"

                # Try to send a heartbeat to verify connectivity
                try:
                    heartbeat_result = await self.exchange_client.send_heartbeat(
                        simulator.endpoint,
                        simulator.session_id,
                        f"validation-{simulator_id}"
                    )

                    if not heartbeat_result.get('success', False):
                        error = heartbeat_result.get('error', 'Heartbeat failed')
                        logger.warning(f"Simulator {simulator_id} heartbeat failed: {error}")
                        
                        # Update status to ERROR since we can't reach it
                        await self.store_manager.simulator_store.update_simulator_status(
                            simulator_id, SimulatorStatus.ERROR
                        )
                        
                        return False, f"Simulator unreachable: {error}"

                except Exception as e:
                    logger.error(f"Error validating simulator {simulator_id}: {e}")
                    
                    # Update status to ERROR since we can't reach it
                    await self.store_manager.simulator_store.update_simulator_status(
                        simulator_id, SimulatorStatus.ERROR
                    )
                    
                    return False, f"Connection error: {str(e)}"

                # Simulator is healthy
                logger.debug(f"Simulator {simulator_id} validation successful")
                return True, ""

            except Exception as e:
                logger.error(f"Error validating simulator health: {e}", exc_info=True)
                span.record_exception(e)
                return False, f"Validation error: {str(e)}"

    async def find_and_validate_simulator(self, session_id: str, user_id: str) -> Tuple[Optional[Simulator], str]:
        """
        Enhanced version that enforces one simulator per user policy and validates health
        
        Args:
            session_id: Session ID
            user_id: User ID

        Returns:
            Tuple of (simulator, error_message)
        """
        with optional_trace_span(self.tracer, "find_and_validate_simulator") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("user_id", user_id)

            logger.info(f"Looking for existing simulators for user {user_id}")

            try:
                # Get ALL active simulators for this user from database
                pool = await self.store_manager.simulator_store._get_pool()
                async with pool.acquire() as conn:
                    rows = await conn.fetch('''
                        SELECT * FROM simulator.instances
                        WHERE user_id = $1 
                        AND status IN ('RUNNING', 'STARTING', 'CREATING')
                        ORDER BY created_at DESC
                    ''', user_id)
                    
                    active_simulators = []
                    for row in rows:
                        simulator = self.store_manager.simulator_store._row_to_entity(row)
                        if simulator:
                            active_simulators.append(simulator)

                if not active_simulators:
                    logger.info(f"No active simulators found for user {user_id}")
                    return None, "No active simulators found"

                logger.info(f"Found {len(active_simulators)} active simulators for user {user_id}")

                # Validate health of all active simulators
                healthy_simulators = []
                unhealthy_simulators = []
                
                for sim in active_simulators:
                    logger.info(f"Validating health of simulator {sim.simulator_id} (status: {sim.status.value})")
                    
                    is_healthy, health_error = await self.validate_simulator_health(sim.simulator_id)
                    
                    if is_healthy:
                        logger.info(f"Simulator {sim.simulator_id} is healthy")
                        healthy_simulators.append(sim)
                    else:
                        logger.warning(f"Simulator {sim.simulator_id} is unhealthy: {health_error}")
                        unhealthy_simulators.append(sim)

                # Clean up all unhealthy simulators
                for sim in unhealthy_simulators:
                    logger.info(f"Marking unhealthy simulator {sim.simulator_id} as ERROR and cleaning up")
                    
                    # Mark as ERROR in database
                    await self.store_manager.simulator_store.update_simulator_status(
                        sim.simulator_id, SimulatorStatus.ERROR
                    )
                    
                    # Clean up Kubernetes resources
                    try:
                        await self.k8s_client.delete_simulator_deployment(sim.simulator_id)
                        logger.info(f"Cleaned up K8s resources for unhealthy simulator {sim.simulator_id}")
                    except Exception as e:
                        logger.error(f"Error cleaning up K8s for unhealthy simulator {sim.simulator_id}: {e}")

                # If NO healthy simulators found, clean up everything and return None
                if len(healthy_simulators) == 0:
                    logger.warning(f"No healthy simulators found for user {user_id}. All simulators were unhealthy and have been cleaned up.")
                    
                    # Also clean up any remaining simulators that might be in other states
                    try:
                        async with pool.acquire() as conn:
                            # Get any remaining simulators for this user that might be in limbo
                            remaining_rows = await conn.fetch('''
                                SELECT * FROM simulator.instances
                                WHERE user_id = $1 
                                AND status NOT IN ('STOPPED', 'ERROR')
                            ''', user_id)
                            
                            for row in remaining_rows:
                                sim_id = row['simulator_id']
                                logger.info(f"Cleaning up remaining simulator {sim_id} in status {row['status']}")
                                
                                # Mark as STOPPED
                                await conn.execute('''
                                    UPDATE simulator.instances 
                                    SET status = 'STOPPED' 
                                    WHERE simulator_id = $1
                                ''', sim_id)
                                
                                # Clean up K8s resources
                                try:
                                    await self.k8s_client.delete_simulator_deployment(sim_id)
                                    logger.info(f"Cleaned up K8s resources for remaining simulator {sim_id}")
                                except Exception as e:
                                    logger.error(f"Error cleaning up K8s for remaining simulator {sim_id}: {e}")
                    
                    except Exception as e:
                        logger.error(f"Error during final cleanup for user {user_id}: {e}")
                    
                    return None, "No healthy simulators found - all cleaned up"

                # Enforce single simulator rule for healthy simulators
                if len(healthy_simulators) > 1:
                    logger.warning(f"User {user_id} has {len(healthy_simulators)} healthy simulators - enforcing single simulator rule")
                    
                    # Sort by preference: STARTING > RUNNING, then by newest
                    healthy_simulators.sort(key=lambda s: (
                        0 if s.status == SimulatorStatus.STARTING else 1,
                        -s.created_at
                    ))
                    
                    # Keep the first one, mark others as STOPPED
                    chosen_simulator = healthy_simulators[0]
                    excess_simulators = healthy_simulators[1:]
                    
                    for sim in excess_simulators:
                        logger.info(f"Marking excess healthy simulator {sim.simulator_id} as STOPPED (keeping {chosen_simulator.simulator_id})")
                        await self.store_manager.simulator_store.update_simulator_status(
                            sim.simulator_id, SimulatorStatus.STOPPED
                        )
                        
                        # Clean up Kubernetes resources
                        try:
                            await self.k8s_client.delete_simulator_deployment(sim.simulator_id)
                            logger.info(f"Cleaned up K8s resources for excess simulator {sim.simulator_id}")
                        except Exception as e:
                            logger.error(f"Error cleaning up K8s for excess simulator {sim.simulator_id}: {e}")

                    return chosen_simulator, ""

                elif len(healthy_simulators) == 1:
                    chosen = healthy_simulators[0]
                    logger.info(f"Using single validated healthy simulator {chosen.simulator_id}")
                    
                    # Update session reference if needed
                    if chosen.session_id != session_id:
                        logger.info(f"Updating simulator {chosen.simulator_id} session reference to {session_id}")
                        await self.store_manager.simulator_store.update_simulator_session(
                            chosen.simulator_id, session_id
                        )
                        chosen.session_id = session_id
                    
                    return chosen, ""

            except Exception as e:
                logger.error(f"Error in find_and_validate_simulator: {e}", exc_info=True)
                span.record_exception(e)
                return None, f"Error during validation: {str(e)}"