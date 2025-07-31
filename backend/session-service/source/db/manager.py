"""
Simplified database connection management for combined schema.
"""
import logging

from source.db.stores.postgres_session_store import PostgresSessionStore
from source.db.stores.postgres_simulator_store import PostgresSimulatorStore

logger = logging.getLogger(__name__)


class StoreManager:
    """Manages PostgreSQL database connections for combined schema"""

    def __init__(self):
        """Initialize database stores"""
        self.session_store = PostgresSessionStore()
        # Updated to use combined schema
        self.simulator_store = PostgresSimulatorStore(
            schema_name="exch_us_equity", 
            table_name="simulator_instances"
        )

    async def connect(self):
        """Connect to PostgreSQL databases"""
        await self.session_store.connect()
        await self.simulator_store.connect()

    async def close(self):
        """Close database connections"""
        await self.session_store.close()
        await self.simulator_store.close()

    async def check_connection(self) -> bool:
        """Check database connection health"""
        return (
                await self.session_store.check_connection() and
                await self.simulator_store.check_connection()
        )