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
        """Get all active exchanges from database"""
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
            
            # Transform the results to match what the orchestrator expects
            # Since exchanges is an array, we'll create one record per exchange
            result = []
            for row in rows:
                # Convert the row to a dict
                row_dict = dict(row)
                
                # Since exchanges is an array, create separate entries for each exchange
                for exchange_name in row_dict['exchanges']:
                    exchange_record = row_dict.copy()
                    # Add fields that the orchestrator expects
                    exchange_record['exchange_id'] = exchange_name  # Use the exchange name as ID
                    exchange_record['exchange_name'] = exchange_name
                    exchange_record['is_active'] = True  # Assume all entries are active
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