# data_access/stores/postgres/postgres_base.py
"""
Base PostgreSQL connection management.
"""
import logging
import asyncio
import asyncpg
from typing import Optional

from opentelemetry import trace

from source.config import config
from source.utils.tracing import optional_trace_span
from source.utils.metrics import track_db_error

logger = logging.getLogger(__name__)


class PostgresBase:
    """Base PostgreSQL connection handler"""

    def __init__(self, db_config=None):
        """Initialize PostgreSQL base connection"""
        self.pool: Optional[asyncpg.Pool] = None
        self.db_config = db_config or config.db
        self._conn_lock = asyncio.Lock()
        self.tracer = trace.get_tracer("postgres_base")

    async def connect(self):
        """Connect to the PostgreSQL database"""
        with optional_trace_span(self.tracer, "pg_connect") as span:
            span.set_attribute("db.system", "postgresql")
            span.set_attribute("db.name", self.db_config.database)
            span.set_attribute("db.host", self.db_config.host)

            async with self._conn_lock:
                if self.pool is not None:
                    return

                max_retries = 5
                retry_count = 0
                retry_delay = 1.0

                while retry_count < max_retries:
                    try:
                        self.pool = await asyncpg.create_pool(
                            host=self.db_config.host,
                            port=self.db_config.port,
                            user=self.db_config.user,
                            password=self.db_config.password,
                            database=self.db_config.database,
                            min_size=self.db_config.min_connections,
                            max_size=self.db_config.max_connections
                        )

                        logger.info("Successfully connected to PostgreSQL database")
                        span.set_attribute("success", True)
                        return

                    except Exception as e:
                        retry_count += 1
                        logger.error(f"PostgreSQL connection error (attempt {retry_count}/{max_retries}): {e}")
                        span.record_exception(e)
                        span.set_attribute("retry_count", retry_count)

                        if retry_count < max_retries:
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            logger.error("Maximum PostgreSQL connection retries reached")
                            span.set_attribute("success", False)
                            track_db_error("pg_connect")
                            raise ConnectionError("Failed to connect to PostgreSQL after multiple retries.") from e

    async def close(self):
        """Close PostgreSQL database connections"""
        async with self._conn_lock:
            if self.pool:
                logger.info("Closing PostgreSQL database connection pool...")
                await self.pool.close()
                self.pool = None
                logger.info("Closed PostgreSQL database connection pool.")
            else:
                logger.info("PostgreSQL connection pool already closed.")

    async def check_connection(self) -> bool:
        """Check PostgreSQL database connection health"""
        if not self.pool:
            logger.warning("Checking connection status: Pool does not exist.")
            return False

        try:
            async with self.pool.acquire() as conn:
                result = await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=5.0)
                is_healthy = (result == 1)
                logger.debug(f"PostgreSQL connection check result: {is_healthy}")
                return is_healthy
        except (asyncio.TimeoutError, Exception) as e:
            logger.error(f"PostgreSQL connection check failed: {e}", exc_info=True)
            return False

    async def _get_pool(self) -> asyncpg.Pool:
        """Internal helper to get the pool, ensuring it's connected"""
        if self.pool is None:
            logger.warning("Accessing pool before explicit connect(). Attempting connection...")
            await self.connect()
        if self.pool is None:
            raise ConnectionError("PostgreSQL pool is not initialized.")
        return self.pool
