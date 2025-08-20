# source/db/connection_pool.py
import asyncpg
import logging
from source.config import config

logger = logging.getLogger('connection_pool')

class DatabasePool:
    """Database connection pool manager"""
    
    def __init__(self):
        self.pool = None
    
    async def initialize(self):
        """Initialize the connection pool"""
        self.pool = await asyncpg.create_pool(
            host=config.db_host,
            port=config.db_port,
            database=config.db_name,
            user=config.db_user,
            password=config.db_password,
            min_size=config.db_min_connections,
            max_size=config.db_max_connections,
            command_timeout=60
        )
        logger.info("Database connection pool initialized")
    
    async def get_pool(self):
        """Get the connection pool"""
        if not self.pool:
            await self.initialize()
        return self.pool
    
    async def close(self):
        """Close the connection pool"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database connection pool closed")