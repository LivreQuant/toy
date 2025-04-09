# In exchange-service/source/db/database.py
import asyncpg
import logging
import os
import asyncio

logger = logging.getLogger('database')


class DatabaseManager:
    def __init__(self):
        self.pool = None
        self.db_host = os.environ.get('DB_HOST', 'postgres')
        self.db_port = int(os.environ.get('DB_PORT', '5432'))
        self.db_name = os.environ.get('DB_NAME', 'opentp')
        self.db_user = os.environ.get('DB_USER', 'opentp')
        self.db_password = os.environ.get('DB_PASSWORD', 'samaral')
        self._conn_lock = asyncio.Lock()

    async def connect(self):
        """Connect to the database"""
        async with self._conn_lock:
            if self.pool is not None:
                return

            try:
                self.pool = await asyncpg.create_pool(
                    host=self.db_host,
                    port=self.db_port,
                    user=self.db_user,
                    password=self.db_password,
                    database=self.db_name,
                    min_size=1,
                    max_size=5
                )
                logger.info("Connected to database")
            except Exception as e:
                logger.error(f"Database connection error: {e}")
                raise

    async def close(self):
        """Close database connections"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Closed database connections")
