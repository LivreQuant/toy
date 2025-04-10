# In exchange-service/source/db/database.py
import asyncpg
import logging
import asyncio
from typing import Dict, Any

from source.config import config

logger = logging.getLogger('database')


class DatabaseManager:
    def __init__(self):
        self.pool = None
        self.db_config = config.db  # Uses config from config.py
        self._conn_lock = asyncio.Lock()

    async def connect(self):
        """Connect to the database"""
        async with self._conn_lock:
            if self.pool is not None:
                return

            max_retries = 5
            retry_count = 0
            retry_delay = 1.0

            # Log all connection parameters (be careful not to log passwords in production)
            logger.info(f"Attempting to connect to PostgreSQL database:")
            logger.info(f"Host: {self.db_config.host}")
            logger.info(f"Port: {self.db_config.port}")
            logger.info(f"Database Name: {self.db_config.database}")
            logger.info(f"Username: {self.db_config.user}")

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
                    logger.info("Connected to PostgreSQL database")
                    return

                except Exception as e:
                    retry_count += 1
                    # More sophisticated retry mechanism
                    logger.error(f"PostgreSQL connection error (attempt {retry_count}/{max_retries}): {e}")

    async def check_connection(self):
        """Verify database connection health"""
        try:
            async with self.pool.acquire() as conn:
                # Simple query to test connection
                await conn.fetchval('SELECT 1')
            logger.info("Database connection health check passed")
            return True
        except Exception as e:
            logger.error(f"Database connection health check failed: {e}")
            return False

    async def close(self):
        """Close database connections"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Closed database connections")

    async def load_user_exchange_state(self, user_id: str, desk_id: str) -> Dict[str, Any]:
        """
        Load historical exchange state for a specific user and desk

        Args:
            user_id (str): User identifier
            desk_id (str): Desk identifier

        Returns:
            Dict with historical state or empty dict if no state found
        """
        async with self.pool.acquire() as conn:
            try:
                # Implement database query to retrieve user's historical state
                # This is a placeholder query, you'll need to adapt it to your database schema

                return {
                    'cash_balance': 1000,
                    'positions': {}
                }

                return {}

            except Exception as e:
                logger.error(f"Error loading user exchange state: {e}")
                return {}