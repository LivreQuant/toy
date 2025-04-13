"""
Comprehensive simulator management operations.
Wraps and extends simulator manager functionality.
"""
import logging
from typing import Tuple, Optional, Dict, Any, AsyncGenerator

from opentelemetry import trace

from source.utils.event_bus import event_bus
from source.utils.retry import retry_with_backoff

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
                # Directly use simulator_manager's create method
                simulator, error = await self.manager.simulator_manager.create_simulator(session_id, user_id)

                if simulator:
                    return simulator.to_dict(), None

                return None, error

            except Exception as e:
                logger.error(f"Simulator creation via manager failed: {e}")
                span.record_exception(e)
                return None, str(e)

    async def stream_exchange_data(
            self,
            session_id: str,
            endpoint: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream exchange data with retry mechanism.
        """

        async def _stream_data():
            async for data in self.manager.exchange_client.stream_exchange_data(
                    endpoint, session_id, f"stream-{session_id}"
            ):
                yield data

        try:
            async for data in retry_with_backoff(
                    _stream_data,
                    max_attempts=5,
                    retriable_exceptions=(ConnectionError, TimeoutError)
            ):
                yield data
        except Exception as e:
            logger.error(f"Exchange data streaming failed: {e}")
            await event_bus.publish('stream_failed',
                                    session_id=session_id,
                                    error=str(e))

    async def stop_simulator(
            self,
            session_id: str,
            force: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Stop simulator, using simulator_manager as primary method.
        """
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

                # Directly use simulator_manager's stop method
                success, error = await self.manager.simulator_manager.stop_simulator(simulator_id)

                # Update session metadata
                await self.manager.update_session_metadata(session_id, {
                    'simulator_status': 'STOPPED',
                    'simulator_id': None,
                    'simulator_endpoint': None
                })

                return success, error

            except Exception as e:
                logger.error(f"Error stopping simulator for session {session_id}: {e}")
                return False, str(e)

    async def run_simulator_heartbeat_loop(self):
        """
        Wrapper around simulator_manager's heartbeat loop
        """
        await self.manager.simulator_manager.run_simulator_heartbeat_loop()
