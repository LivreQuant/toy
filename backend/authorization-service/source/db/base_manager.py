# source/db/base_manager.py
import logging
import asyncpg
import os
from opentelemetry import trace

from source.utils.tracing import optional_trace_span
from source.utils.metrics import track_db_connection

logger = logging.getLogger('database')

class BaseDatabaseManager:
    def __init__(self):
        self.pool = None
        self.db_config = {
            'host': os.getenv('DB_HOST', 'postgres'),
            'port': int(os.getenv('DB_PORT', '5432')),
            'database': os.getenv('DB_NAME', 'opentp'),
            'user': os.getenv('DB_USER', 'opentp'),
            'password': os.getenv('DB_PASSWORD', 'samaral')
        }
        self.min_connections = int(os.getenv('DB_MIN_CONNECTIONS', '1'))
        self.max_connections = int(os.getenv('DB_MAX_CONNECTIONS', '10'))
        self.tracer = trace.get_tracer("db_manager")

    async def connect(self):
        """Create the database connection pool"""
        with optional_trace_span(self.tracer, "db_connect") as span:
            if self.pool:
                return

            try:
                span.set_attribute("db.system", "postgresql")
                span.set_attribute("db.name", self.db_config['database'])
                span.set_attribute("db.user", self.db_config['user'])
                span.set_attribute("db.host", self.db_config['host'])
                span.set_attribute("db.port", self.db_config['port'])
                
                self.pool = await asyncpg.create_pool(
                    min_size=self.min_connections,
                    max_size=self.max_connections,
                    **self.db_config
                )
                logger.info("Database connection established")
                span.set_attribute("success", True)
                track_db_connection(True)
            except Exception as e:
                logger.error(f"Database connection failed: {e}")
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                track_db_connection(False)
                raise

    async def close(self):
        """Close all database connections"""
        with optional_trace_span(self.tracer, "db_close") as span:
            if self.pool:
                await self.pool.close()
                self.pool = None
                logger.info("Database connections closed")
                span.set_attribute("success", True)

    async def check_connection(self):
        """Check if database connection is working"""
        with optional_trace_span(self.tracer, "db_check_connection") as span:
            if not self.pool:
                try:
                    await self.connect()
                    span.set_attribute("success", True)
                    return True
                except:
                    span.set_attribute("success", False)
                    return False

            try:
                async with self.pool.acquire() as conn:
                    await conn.execute("SELECT 1")
                    span.set_attribute("success", True)
                    return True
            except Exception as e:
                logger.error(f"Database connection check failed: {e}")
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                return False