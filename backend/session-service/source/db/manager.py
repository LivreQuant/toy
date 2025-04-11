"""
Centralized database connection management.
"""
import logging

from source.db.stores.postgres_session_store import PostgresSessionStore
from source.db.stores.postgres_simulator_store import PostgresSimulatorStore

logger = logging.getLogger(__name__)


class StoreManager:
    """Manages PostgreSQL database connections"""

    def __init__(self):
        """Initialize database stores"""
        self.session_store = PostgresSessionStore()
        self.simulator_store = PostgresSimulatorStore()

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
