# source/db/connection_pool.py
import logging
import asyncio
import asyncpg
from typing import Optional

from source.config import config
from source.utils.metrics import set_db_connection_count

logger = logging.getLogger('db_connection_pool')


class DatabasePool:
    """Singleton database connection pool with enhanced error handling"""
    _instance = None
    _pool = None
    _lock = asyncio.Lock()
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabasePool, cls).__new__(cls)
        return cls._instance

    async def initialize(self):
        """Initialize the database connection pool - required by main.py"""
        if self._initialized:
            logger.info("Database pool already initialized")
            return
            
        async with self._lock:
            if self._initialized:
                return
                
            logger.info("Initializing database connection pool...")
            await self._create_pool()
            self._initialized = True
            logger.info("Database pool initialization complete")

    async def get_pool(self) -> asyncpg.Pool:
        """Get or create the database connection pool"""
        if not self._initialized:
            await self.initialize()
            
        async with self._lock:
            if self._pool is None:
                await self._create_pool()
            return self._pool

    async def _create_pool(self):
        """Create the database connection pool with enhanced retry logic"""
        max_retries = 10
        retry_count = 0
        base_delay = 2.0
        max_delay = 30.0

        while retry_count < max_retries:
            try:
                logger.info(f"Creating database connection pool (attempt {retry_count + 1}/{max_retries})")
                logger.info(f"Connecting to: {config.db_host}:{config.db_port}/{config.db_name} as {config.db_user}")

                # REMOVED JIT PARAMETER - this was causing the issue with pgbouncer
                self._pool = await asyncpg.create_pool(
                    min_size=config.db_min_connections,
                    max_size=config.db_max_connections,
                    command_timeout=30,
                    max_queries=50000,
                    max_inactive_connection_lifetime=300,
                    timeout=30,
                    host=config.db_host,
                    port=config.db_port,
                    user=config.db_user,
                    password=config.db_password,
                    database=config.db_name,
                    server_settings={
                        'application_name': f'fund-service-{config.environment}'
                        # REMOVED 'jit': 'off' - pgbouncer doesn't support this
                    }
                )

                # Test the connection with a simple query
                logger.info("Testing database connection...")
                async with self._pool.acquire() as conn:
                    result = await conn.fetchval('SELECT 1')
                    logger.info(f"Database connection successful. Test query result: {result}")

                # Report connection count in metrics
                set_db_connection_count(config.db_min_connections)

                logger.info("Database connection pool established successfully")
                return

            except Exception as e:
                retry_count += 1
                logger.error(f"Database connection error (attempt {retry_count}/{max_retries}): {e}")
                
                # Clean up failed pool
                if self._pool:
                    try:
                        await self._pool.close()
                    except:
                        pass
                    self._pool = None

                if retry_count < max_retries:
                    # Exponential backoff with max delay
                    delay = min(base_delay * (2 ** (retry_count - 1)), max_delay)
                    logger.info(f"Retrying database connection in {delay:.1f} seconds...")
                    await asyncio.sleep(delay)
                else:
                    logger.error("Maximum database connection retries reached")
                    raise

    async def close(self):
        """Close the database connection pool"""
        async with self._lock:
            if self._pool:
                await self._pool.close()
                self._pool = None
                self._initialized = False
                logger.info("Closed database connection pool")

                # Update connection count in metrics
                set_db_connection_count(0)

    async def check_connection(self) -> bool:
        """Check if database connection is working"""
        try:
            if not self._initialized:
                return False
                
            pool = await self.get_pool()
            async with pool.acquire() as conn:
                await conn.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False

    @property
    def is_initialized(self) -> bool:
        """Check if pool is initialized"""
        return self._initialized and self._pool is not None

    async def health_check(self) -> dict:
        """Perform comprehensive database health check"""
        health_status = {
            'status': 'unhealthy',
            'initialized': self._initialized,
            'pool_available': self._pool is not None,
            'connection_test': False,
            'error': None
        }
        
        try:
            if not self._initialized:
                health_status['error'] = 'Pool not initialized'
                return health_status
                
            if not self._pool:
                health_status['error'] = 'Pool not available'
                return health_status
                
            # Test actual connection
            async with self._pool.acquire() as conn:
                await conn.fetchval('SELECT 1')
                health_status['connection_test'] = True
                health_status['status'] = 'healthy'
                
        except Exception as e:
            health_status['error'] = str(e)
            logger.error(f"Database health check failed: {e}")
            
        return health_status