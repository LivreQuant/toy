# source/db/database.py
import asyncpg
import logging
import asyncio
from typing import Dict, List, Any

from source.config import config

logger = logging.getLogger(__name__)

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

            # Log connection attempt
            logger.info(f"Attempting to connect to PostgreSQL database at {self.db_config.host}:{self.db_config.port}")

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
                    logger.error(f"PostgreSQL connection error (attempt {retry_count}/{max_retries}): {e}")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff

            raise Exception("Failed to connect to database after multiple attempts")

    async def close(self):
        """Close database connections"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Closed database connections")

    async def save_market_data(self, market_data: List[Dict[str, Any]]):
        """
        Save market data to the market_data table
        
        Args:
            market_data: List of market data records
        """
        if not self.pool:
            logger.error("Cannot save market data: database not connected")
            return False
            
        try:
            async with self.pool.acquire() as conn:
                # Begin transaction
                async with conn.transaction():
                    # Prepare batch insert statement
                    stmt = await conn.prepare('''
                        INSERT INTO marketdata.market_data(
                            symbol, timestamp, open, high, low, close, 
                            volume, trade_count, vwap
                        ) VALUES($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ''')
                    
                    # Execute batch insert
                    records = [
                        (
                            md['symbol'],
                            md['timestamp'],
                            md['open'],
                            md['high'],
                            md['low'],
                            md['close'],
                            md['volume'],
                            md.get('trade_count', 0),
                            md.get('vwap', 0.0)
                        )
                        for md in market_data
                    ]
                    
                    await stmt.executemany(records)
                    
                logger.info(f"Saved {len(market_data)} market data records to database")
                return True
                
        except Exception as e:
            logger.error(f"Error saving market data to database: {e}")
            return False
        