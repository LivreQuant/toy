import logging
import asyncio
import asyncpg
import time
from typing import Optional

from source.config import config
from source.utils.metrics import track_db_operation, set_db_connection_count

logger = logging.getLogger('db_connection_pool')

class DatabasePool:
    """Singleton database connection pool"""
    _instance = None
    _pool = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabasePool, cls).__new__(cls)
        return cls._instance
        
    async def get_pool(self) -> asyncpg.Pool:
        """Get or create the database connection pool"""
        async with self._lock:
            if self._pool is None:
                await self._create_pool()
            return self._pool
    
    async def _create_pool(self):
        """Create the database connection pool with retry logic"""
        max_retries = 5
        retry_count = 0
        retry_delay = 1.0

        while retry_count < max_retries:
            try:
                logger.info(f"Creating database connection pool (attempt {retry_count+1}/{max_retries})")
                
                self._pool = await asyncpg.create_pool(
                    min_size=config.db_min_connections,
                    max_size=config.db_max_connections,
                    command_timeout=10,
                    host=config.db_host,
                    port=config.db_port,
                    user=config.db_user,
                    password=config.db_password,
                    database=config.db_name
                )

                # Report connection count in metrics
                set_db_connection_count(config.db_min_connections)

                logger.info("Database connection pool established")
                return
            except Exception as e:
                retry_count += 1
                logger.error(f"Database connection error (attempt {retry_count}/{max_retries}): {e}")

                if retry_count < max_retries:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error("Maximum database connection retries reached")
                    raise

    async def close(self):
        """Close the database connection pool"""
        async with self._lock:
            if self._pool:
                await self._pool.close()
                self._pool = None
                logger.info("Closed database connection pool")
                
                # Update connection count in metrics
                set_db_connection_count(0)
                
    async def check_connection(self) -> bool:
        """Check if database connection is working"""
        try:
            pool = await self.get_pool()
            async with pool.acquire() as conn:
                await conn.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False
        