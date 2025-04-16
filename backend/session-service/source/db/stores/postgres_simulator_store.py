# data_access/stores/postgres/postgres_simulator_store.py
"""
Handles PostgreSQL interactions for Simulator data.
Simplified for single simulator per session service.
"""
import logging
from typing import Optional

from source.models.simulator import Simulator, SimulatorStatus
from source.utils.metrics import track_db_operation, track_db_error, TimedOperation
from source.utils.tracing import optional_trace_span
from source.db.stores.postgres_base import PostgresRepository

logger = logging.getLogger('pg_simulator_store')


class PostgresSimulatorStore(PostgresRepository[Simulator]):
    """PostgreSQL store for simulator data."""

    def __init__(self, db_config=None):
        """Initialize PostgreSQL simulator store."""
        super().__init__(
            entity_class=Simulator,
            schema_name="simulator",
            table_name="instances",
            id_field="simulator_id",
            tracer_name="postgres_simulator_store",
            db_config=db_config
        )
        logger.info("PostgresSimulatorStore initialized.")

    async def create_simulator(self, simulator: Simulator) -> bool:
        """
        Create a new simulator record in PostgreSQL.
        """
        with optional_trace_span(self.tracer, "pg_store_create_simulator") as span:
            span.set_attribute("simulator_id", simulator.simulator_id)
            span.set_attribute("session_id", simulator.session_id)

            try:
                pool = await self._get_pool()
                with TimedOperation(track_db_operation, "pg_create_simulator"):
                    async with pool.acquire() as conn:
                        await conn.execute('''
                            INSERT INTO simulator.instances (
                                simulator_id, session_id, user_id, status, 
                                endpoint, created_at, last_active
                            ) VALUES ($1, $2, $3, $4, $5, to_timestamp($6), to_timestamp($7))
                        ''',
                                           simulator.simulator_id,
                                           simulator.session_id,
                                           'rmv',
                                           simulator.status.value,
                                           simulator.endpoint,
                                           simulator.created_at,
                                           simulator.last_active
                                           )
                        return True
            except Exception as e:
                logger.error(f"Error creating simulator in PostgreSQL: {e}")
                span.record_exception(e)
                track_db_error("pg_create_simulator")
                return False

    async def update_simulator_endpoint(self, simulator_id: str, endpoint: str) -> bool:
        """
        Update simulator endpoint in PostgreSQL.
        """
        with optional_trace_span(self.tracer, "pg_store_update_simulator_endpoint") as span:
            span.set_attribute("simulator_id", simulator_id)
            span.set_attribute("endpoint", endpoint)

            try:
                pool = await self._get_pool()
                with TimedOperation(track_db_operation, "pg_update_simulator_endpoint"):
                    async with pool.acquire() as conn:
                        result = await conn.execute('''
                            UPDATE simulator.instances
                            SET endpoint = $1, last_active = NOW()
                            WHERE simulator_id = $2
                        ''', endpoint, simulator_id)
                        return 'UPDATE 1' in result
            except Exception as e:
                logger.error(f"Error updating simulator endpoint in PostgreSQL: {e}")
                span.record_exception(e)
                track_db_error("pg_update_simulator_endpoint")
                return False

    async def update_simulator_status(self, simulator_id: str, status: SimulatorStatus) -> bool:
        """
        Update simulator status in PostgreSQL.
        """
        with optional_trace_span(self.tracer, "pg_store_update_simulator_status") as span:
            span.set_attribute("simulator_id", simulator_id)
            span.set_attribute("status", status.value)

            try:
                pool = await self._get_pool()
                with TimedOperation(track_db_operation, "pg_update_simulator_status"):
                    async with pool.acquire() as conn:
                        result = await conn.execute('''
                            UPDATE simulator.instances
                            SET status = $1, last_active = NOW()
                            WHERE simulator_id = $2
                        ''', status.value, simulator_id)
                        return 'UPDATE 1' in result
            except Exception as e:
                logger.error(f"Error updating simulator status in PostgreSQL: {e}")
                span.record_exception(e)
                track_db_error("pg_update_simulator_status")
                return False

    async def get_simulator(self, simulator_id: str) -> Optional[Simulator]:
        """
        Get simulator by ID.
        """
        with optional_trace_span(self.tracer, "pg_store_get_simulator") as span:
            span.set_attribute("simulator_id", simulator_id)

            try:
                pool = await self._get_pool()
                with TimedOperation(track_db_operation, "pg_get_simulator"):
                    async with pool.acquire() as conn:
                        row = await conn.fetchrow('''
                            SELECT * FROM simulator.instances
                            WHERE simulator_id = $1
                        ''', simulator_id)

                        if not row:
                            return None

                        return self._row_to_entity(row)
            except Exception as e:
                logger.error(f"Error getting simulator {simulator_id} from PostgreSQL: {e}")
                span.record_exception(e)
                track_db_error("pg_get_simulator")
                return None

    async def update_simulator_session(self, simulator_id: str, session_id: str) -> bool:
        """
        Update the session ID for a simulator.
        Used when reusing a simulator across different sessions.

        Args:
            simulator_id: The simulator ID to update
            session_id: The new session ID

        Returns:
            True if successful, False otherwise
        """
        with optional_trace_span(self.tracer, "pg_store_update_simulator_session") as span:
            span.set_attribute("simulator_id", simulator_id)
            span.set_attribute("session_id", session_id)

            try:
                pool = await self._get_pool()
                with TimedOperation(track_db_operation, "pg_update_simulator_session"):
                    async with pool.acquire() as conn:
                        result = await conn.execute('''
                            UPDATE simulator.instances
                            SET session_id = $1, last_active = NOW()
                            WHERE simulator_id = $2
                        ''', session_id, simulator_id)
                        return 'UPDATE 1' in result
            except Exception as e:
                logger.error(f"Error updating simulator session in PostgreSQL: {e}")
                span.record_exception(e)
                track_db_error("pg_update_simulator_session")
                return False

    async def get_simulator_by_session(self, session_id: str) -> Optional[Simulator]:
        """
        Get simulator for a specific session ID.
        """
        with optional_trace_span(self.tracer, "pg_store_get_simulator_by_session") as span:
            span.set_attribute("session_id", session_id)

            try:
                pool = await self._get_pool()
                with TimedOperation(track_db_operation, "pg_get_simulator_by_session"):
                    async with pool.acquire() as conn:
                        row = await conn.fetchrow('''
                            SELECT * FROM simulator.instances
                            WHERE session_id = $1
                            ORDER BY created_at DESC
                            LIMIT 1
                        ''', session_id)

                        if not row:
                            return None

                        return self._row_to_entity(row)
            except Exception as e:
                logger.error(f"Error getting simulator for session {session_id} from PostgreSQL: {e}")
                span.record_exception(e)
                track_db_error("pg_get_simulator_by_session")
                return None
