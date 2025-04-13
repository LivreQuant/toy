"""
Simplified simulator management operations for singleton mode.
"""
import logging
from typing import Tuple, Optional, Dict, Any, AsyncGenerator

from opentelemetry import trace

from source.utils.retry import retry_with_backoff_generator

logger = logging.getLogger('simulator_operations')


class SimulatorOperations:
    def __init__(self, session_manager):
        """
        Initialize with session manager reference

        Args:
            session_manager: Parent SessionManager instance
        """
        self.manager = session_manager
        self.tracer = trace.get_tracer("simulator_operations")

    async def create_simulator(
            self,
            session_id: str,
            user_id: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Creates simulator using simulator_manager, with enhanced error handling.
        """
        with self.tracer.start_as_current_span("create_simulator") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("user_id", user_id)

            try:
                # Check if there's already a simulator for this session
                session_metadata = await self.manager.get_session_metadata()

                if session_metadata and session_metadata.get('simulator_id'):
                    simulator_id = session_metadata.get('simulator_id')
                    simulator_status = session_metadata.get('simulator_status')
                    endpoint = session_metadata.get('simulator_endpoint')

                    # If already running, just return existing one
                    if simulator_status in ['RUNNING', 'STARTING', 'CREATING'] and endpoint:
                        logger.info(f"Reusing existing simulator {simulator_id}")
                        return {
                            'simulator_id': simulator_id,
                            'status': simulator_status,
                            'endpoint': endpoint
                        }, None

                # Create a new simulator
                simulator, error = await self.manager.simulator_manager.create_simulator(session_id, user_id)

                if simulator:
                    # Update session metadata
                    await self.manager.update_session_metadata({
                        'simulator_id': simulator.simulator_id,
                        'simulator_status': simulator.status.value,
                        'simulator_endpoint': simulator.endpoint
                    })

                    return simulator.to_dict(), None

                return None, error

            except Exception as e:
                logger.error(f"Simulator creation via manager failed: {e}")
                span.record_exception(e)
                return None, str(e)

    async def stream_exchange_data(
            self,
            endpoint: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream exchange data with retry mechanism.
        """

        async def _stream_data():
            session_id = self.manager.session_id
            async for data in self.manager.exchange_client.stream_exchange_data(
                    endpoint, session_id, f"stream-{session_id}"
            ):
                yield data

        # Use our retry generator to handle connection issues
        async for data in retry_with_backoff_generator(
                _stream_data,
                max_attempts=5,
                retriable_exceptions=(ConnectionError, TimeoutError)
        ):
            yield data

    async def stop_simulator(
            self,
            force: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Stop simulator associated with the session.
        """
        session_id = self.manager.session_id
        with self.tracer.start_as_current_span("stop_simulator") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("force", force)

            try:
                # Get simulator from session metadata
                session = await self.manager.store_manager.session_store.get_session_from_db(
                    session_id,
                    skip_activity_check=force
                )

                if not session:
                    return False, "Session not found"

                metadata = session.metadata
                simulator_id = getattr(metadata, 'simulator_id', None)

                if not simulator_id:
                    return True, ""

                # Use simulator_manager's stop method
                success, error = await self.manager.simulator_manager.stop_simulator(simulator_id)

                # Update session metadata
                await self.manager.update_session_metadata({
                    'simulator_status': 'STOPPED',
                    'simulator_id': None,
                    'simulator_endpoint': None
                })

                return success, error

            except Exception as e:
                logger.error(f"Error stopping simulator: {e}")
                return False, str(e)