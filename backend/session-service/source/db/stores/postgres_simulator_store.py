# data_access/stores/postgres/postgres_simulator_store.py
"""
Handles PostgreSQL interactions for Simulator data.
"""
import logging
import time
from typing import Optional

from opentelemetry import trace

from source.models.simulator import Simulator, SimulatorStatus
from source.utils.metrics import track_db_operation, track_db_error, TimedOperation, track_cleanup_operation
from source.utils.tracing import optional_trace_span

from source.db.stores.postgres_base import PostgresBase

logger = logging.getLogger('pg_simulator_store')


class PostgresSimulatorStore(PostgresBase):
    """PostgreSQL store for simulator data."""

    def __init__(self):
        """Initialize PostgreSQL simulator store."""
        super().__init__()
        self.tracer = trace.get_tracer("postgres_simulator_store")
        logger.info("PostgresSimulatorStore initialized.")

    async def create_simulator(self, simulator: Simulator) -> bool:
        """
        Create a new simulator record in PostgreSQL.
        """
        with optional_trace_span(self.tracer, "pg_store_create_simulator") as span:
            span.set_attribute("simulator_id", simulator.simulator_id)
            span.set_attribute("session_id", simulator.session_id)
            span.set_attribute("user_id", simulator.user_id)

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
                                           simulator.user_id,
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
                        # First, get current status
                        current_status = await conn.fetchval('''
                            SELECT status FROM simulator.instances
                            WHERE simulator_id = $1
                        ''', simulator_id)

                        # Prevent changing from terminal states
                        if current_status in [SimulatorStatus.STOPPED.value, SimulatorStatus.ERROR.value]:
                            if status == SimulatorStatus.RUNNING:
                                logger.warning(
                                    f"Attempted to change {current_status} simulator {simulator_id} to RUNNING. Not allowed.")
                                return False

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

    async def update_simulator_activity(self, simulator_id: str) -> bool:
        """
        Update simulator last active time.
        """
        with optional_trace_span(self.tracer, "pg_store_update_simulator_activity") as span:
            span.set_attribute("simulator_id", simulator_id)

            try:
                current_time = time.time()
                pool = await self._get_pool()

                with TimedOperation(track_db_operation, "pg_update_simulator_activity"):
                    async with pool.acquire() as conn:
                        result = await conn.execute('''
                            UPDATE simulator.instances
                            SET last_active = to_timestamp($1)
                            WHERE simulator_id = $2
                            AND status = $3
                        ''', current_time, simulator_id, SimulatorStatus.RUNNING.value)

                        return 'UPDATE 1' in result
            except Exception as e:
                logger.error(f"Error updating simulator activity in PostgreSQL: {e}")
                span.record_exception(e)
                track_db_error("pg_update_simulator_activity")
                return False

    async def get_simulator(self, simulator_id: str) -> Optional[Simulator]:
        """
        Get simulator by ID from PostgreSQL.
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

                        return Simulator(
                            simulator_id=row['simulator_id'],
                            session_id=row['session_id'],
                            user_id=row['user_id'],
                            status=SimulatorStatus(row['status']),
                            endpoint=row['endpoint'],
                            created_at=row['created_at'].timestamp(),
                            last_active=row['last_active'].timestamp(),
                        )
            except Exception as e:
                logger.error(f"Error getting simulator from PostgreSQL: {e}")
                span.record_exception(e)
                track_db_error("pg_get_simulator")
                return None

    # (Other methods like get_simulator_by_session, get_active_user_simulators, etc.
    # would follow a similar pattern to the ones in your previous implementation)

    async def cleanup_inactive_simulators(self, inactivity_timeout: int) -> int:
        """
        Mark simulators as STOPPED if they've been inactive beyond the timeout.
        """
        with optional_trace_span(self.tracer, "pg_store_cleanup_inactive_simulators") as span:
            span.set_attribute("inactivity_timeout", inactivity_timeout)

            try:
                pool = await self._get_pool()
                with TimedOperation(track_db_operation, "pg_cleanup_inactive_simulators"):
                    async with pool.acquire() as conn:
                        # Mark simulators as STOPPED if they've been inactive
                        result = await conn.execute('''
                            UPDATE simulator.instances
                            SET status = $1
                            WHERE status != $1
                            AND last_active < NOW() - INTERVAL '1 second' * $2
                        ''', SimulatorStatus.STOPPED.value, inactivity_timeout)

                        count = int(result.split()[-1]) if result else 0
                        span.set_attribute("simulators_cleaned", count)

                        if count > 0:
                            logger.info(f"Marked {count} inactive simulators as STOPPED")
                            track_cleanup_operation("simulators", count)
                        return count
            except Exception as e:
                logger.error(f"Error cleaning up inactive simulators in PostgreSQL: {e}")
                span.record_exception(e)
                track_db_error("pg_cleanup_inactive_simulators")
                return 0
