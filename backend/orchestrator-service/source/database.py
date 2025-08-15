# orchestrator/database.py
import os
import asyncpg
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.pool = None
    
    async def init(self):
        """Initialize database connection pool"""
        self.pool = await asyncpg.create_pool(
            host=os.getenv('DB_HOST', 'pgbouncer'),
            port=int(os.getenv('DB_PORT', '5432')),
            database=os.getenv('DB_NAME', 'opentp'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            min_size=2,
            max_size=10
        )
        logger.info("Database connection pool initialized")
    
    async def get_active_exchanges(self):
        """Get all active exchanges from database"""
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT exch_id, exchange_id, exchange_type, exchange_name,
                       pre_open_time, open_time, close_time, post_close_time, 
                       timezone, is_active
                FROM exch_us_equity.metadata 
                WHERE is_active = true
                ORDER BY exchange_id
            """)
    
    async def get_exchange_by_id(self, exch_id: str):
        """Get specific exchange by ID"""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("""
                SELECT exch_id, exchange_id, exchange_type, exchange_name,
                       pre_open_time, open_time, close_time, post_close_time, 
                       timezone, is_active
                FROM exch_us_equity.metadata 
                WHERE exch_id = $1 AND is_active = true
            """, exch_id)
    
    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")