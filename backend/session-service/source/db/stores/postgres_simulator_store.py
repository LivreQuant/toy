"""
Handles PostgreSQL interactions for Simulator data in combined schema.
"""
import logging
from typing import Optional

from source.models.simulator import Simulator, SimulatorStatus
from source.utils.metrics import track_db_operation, track_db_error, TimedOperation
from source.utils.tracing import optional_trace_span
from source.db.stores.postgres_base import PostgresRepository

logger = logging.getLogger('pg_simulator_store')


class PostgresSimulatorStore(PostgresRepository[Simulator]):
    """PostgreSQL store for simulator data in combined schema."""

    def __init__(self, schema_name="exch_us_equity", table_name="simulator_instances", db_config=None):
        """Initialize PostgreSQL simulator store for combined schema."""
        super().__init__(
            entity_class=Simulator,
            schema_name=schema_name,
            table_name=table_name,
            id_field="simulator_id",
            tracer_name="postgres_simulator_store",
            db_config=db_config
        )
        logger.info(f"PostgresSimulatorStore initialized for {schema_name}.{table_name}")

    async def get_simulator_by_user(self, book_id: str) -> Optional[Simulator]:
        """Get simulator for a specific user"""
        with optional_trace_span(self.tracer, "pg_store_get_simulator_by_user") as span:
            span.set_attribute("book_id", book_id)

            try:
                pool = await self._get_pool()
                with TimedOperation(track_db_operation, "pg_get_simulator_by_user"):
                    async with pool.acquire() as conn:
                        row = await conn.fetchrow(f'''
                            SELECT * FROM {self.full_table_name}
                            WHERE book_id = $1 AND status = 'RUNNING'
                            LIMIT 1
                        ''', book_id)

                        if not row:
                            return None

                        return self._row_to_entity(row)
            except Exception as e:
                logger.error(f"Error getting simulator for user {book_id}: {e}")
                span.record_exception(e)
                track_db_error("pg_get_simulator_by_user")
                return None

    async def update_simulator_activity(self, simulator_id: str) -> bool:
        """Update simulator last activity timestamp"""
        with optional_trace_span(self.tracer, "pg_store_update_simulator_activity") as span:
            span.set_attribute("simulator_id", simulator_id)

            try:
                pool = await self._get_pool()
                with TimedOperation(track_db_operation, "pg_update_simulator_activity"):
                    async with pool.acquire() as conn:
                        result = await conn.execute(f'''
                            UPDATE {self.full_table_name}
                            SET last_active = NOW()
                            WHERE simulator_id = $1
                        ''', simulator_id)
                        return 'UPDATE 1' in result
            except Exception as e:
                logger.error(f"Error updating simulator activity: {e}")
                span.record_exception(e)
                track_db_error("pg_update_simulator_activity")
                return False

    async def get_simulator(self, simulator_id: str) -> Optional[Simulator]:
        """Get simulator by ID"""
        with optional_trace_span(self.tracer, "pg_store_get_simulator") as span:
            span.set_attribute("simulator_id", simulator_id)

            try:
                pool = await self._get_pool()
                with TimedOperation(track_db_operation, "pg_get_simulator"):
                    async with pool.acquire() as conn:
                        row = await conn.fetchrow(f'''
                            SELECT * FROM {self.full_table_name}
                            WHERE simulator_id = $1
                        ''', simulator_id)

                        if not row:
                            return None

                        return self._row_to_entity(row)
            except Exception as e:
                logger.error(f"Error getting simulator {simulator_id}: {e}")
                span.record_exception(e)
                track_db_error("pg_get_simulator")
                return None