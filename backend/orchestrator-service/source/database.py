# database.py
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
        """Get all active exchanges from database - ONE RECORD PER EXCHANGE SERVICE"""
        async with self.pool.acquire() as conn:
            # Query using actual schema columns
            rows = await conn.fetch("""
                SELECT exch_id, 
                       exchange_type, 
                       exchanges,
                       timezone,
                       pre_market_open as pre_open_time,
                       market_open as open_time, 
                       market_close as close_time,
                       post_market_close as post_close_time,
                       endpoint,
                       pod_name,
                       namespace,
                       last_snap,
                       updated_time
                FROM exch_us_equity.metadata 
                ORDER BY exch_id
            """)
            
            # Transform the results - ONE RECORD PER EXCHANGE SERVICE (not per exchange name)
            result = []
            for row in rows:
                # Convert the row to a dict
                row_dict = dict(row)
                
                # Use the first exchange name as the primary exchange ID
                primary_exchange = row_dict['exchanges'][0] if row_dict['exchanges'] else 'UNKNOWN'
                
                # Create ONE record per exchange service
                exchange_record = row_dict.copy()
                exchange_record['exchange_id'] = primary_exchange
                exchange_record['exchange_name'] = primary_exchange
                exchange_record['is_active'] = True
                result.append(exchange_record)
            
            return result
    
    async def get_exchange_by_id(self, exch_id: str):
        """Get specific exchange by ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT exch_id, 
                       exchange_type, 
                       exchanges,
                       timezone,
                       pre_market_open as pre_open_time,
                       market_open as open_time, 
                       market_close as close_time,
                       post_market_close as post_close_time,
                       endpoint,
                       pod_name,
                       namespace,
                       last_snap,
                       updated_time
                FROM exch_us_equity.metadata 
                WHERE exch_id = $1
            """, exch_id)
            
            if row:
                # Convert to dict and add expected fields
                row_dict = dict(row)
                # For individual lookup, use the first exchange name if available
                if row_dict['exchanges']:
                    row_dict['exchange_id'] = row_dict['exchanges'][0]
                    row_dict['exchange_name'] = row_dict['exchanges'][0]
                else:
                    row_dict['exchange_id'] = f"exchange-{exch_id}"
                    row_dict['exchange_name'] = f"Exchange {exch_id}"
                
                row_dict['is_active'] = True
                return row_dict
            
            return None
    
    async def get_exchanges_by_name(self, exchange_name: str):
        """Get exchanges that contain a specific exchange name"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT exch_id, 
                       exchange_type, 
                       exchanges,
                       timezone,
                       pre_market_open as pre_open_time,
                       market_open as open_time, 
                       market_close as close_time,
                       post_market_close as post_close_time,
                       endpoint,
                       pod_name,
                       namespace,
                       last_snap,
                       updated_time
                FROM exch_us_equity.metadata 
                WHERE $1 = ANY(exchanges)
            """, exchange_name)
            
            result = []
            for row in rows:
                row_dict = dict(row)
                row_dict['exchange_id'] = exchange_name
                row_dict['exchange_name'] = exchange_name
                row_dict['is_active'] = True
                result.append(row_dict)
            
            return result
    
    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")