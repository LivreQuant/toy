# source/db/state_repository.py
import logging

from source.db.connection_pool import DatabasePool

logger = logging.getLogger('state_repository')

class StateRepository:
    """Data access layer for session and authorization related operations"""

    def __init__(self):
        """Initialize the session repository"""
        self.db_pool = DatabasePool()

    async def check_connection(self) -> bool:
        """Check if database connection is working"""
        try:
            pool = await self.db_pool.get_pool()
            async with pool.acquire() as conn:
                await conn.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False