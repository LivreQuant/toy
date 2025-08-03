# source/db/database.py
import asyncpg
import logging
import asyncio
import uuid
from typing import Dict, List, Any
from datetime import datetime

from source.config import config

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.pool = None
        self.db_config = config.db
        self._conn_lock = asyncio.Lock()

    async def connect(self):
        """Connect to the database"""
        async with self._conn_lock:
            if self.pool is not None:
                return

            max_retries = 5
            retry_count = 0
            retry_delay = 1.0

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
                    await self._ensure_schema_exists()
                    return

                except Exception as e:
                    retry_count += 1
                    logger.error(f"PostgreSQL connection error (attempt {retry_count}/{max_retries}): {e}")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2

            raise Exception("Failed to connect to database after multiple attempts")

    async def _ensure_schema_exists(self):
        """Ensure the exch_us_equity schema exists"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("CREATE SCHEMA IF NOT EXISTS exch_us_equity")
                
                # Create equity_data table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS exch_us_equity.equity_data (
                        timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                        symbol VARCHAR(20) NOT NULL,
                        currency VARCHAR(3) NOT NULL,
                        open DECIMAL(12,4) NOT NULL,
                        high DECIMAL(12,4) NOT NULL,
                        low DECIMAL(12,4) NOT NULL,
                        close DECIMAL(12,4) NOT NULL,
                        vwap DECIMAL(12,4) NOT NULL,
                        vwas DECIMAL(12,4) NOT NULL,
                        vwav DECIMAL(12,4) NOT NULL,
                        volume BIGINT NOT NULL,
                        count INTEGER NOT NULL
                    )
                """)
                
                # Create fx_data table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS exch_us_equity.fx_data (
                        timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                        from_currency VARCHAR(3) NOT NULL,
                        to_currency VARCHAR(3) NOT NULL,
                        rate DECIMAL(12,6) NOT NULL
                    )
                """)
                
                # Create indexes
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_equity_data_timestamp ON exch_us_equity.equity_data(timestamp)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_equity_data_symbol ON exch_us_equity.equity_data(symbol)")
                await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_equity_data_unique ON exch_us_equity.equity_data(timestamp, symbol)")
                
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_fx_data_timestamp ON exch_us_equity.fx_data(timestamp)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_fx_data_currencies ON exch_us_equity.fx_data(from_currency, to_currency)")
                await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_fx_data_unique ON exch_us_equity.fx_data(timestamp, from_currency, to_currency)")
                
                logger.info("Database schema initialized successfully")
                
        except Exception as e:
            logger.error(f"Error ensuring schema exists: {e}")

    async def close(self):
        """Close database connections"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Closed database connections")

    def _truncate_to_minute(self, dt: datetime) -> datetime:
        """Truncate datetime to exact minute boundary (remove seconds and microseconds)"""
        return dt.replace(second=0, microsecond=0)

    async def save_equity_data(self, equity_data: List[Dict[str, Any]], timestamp: datetime):
        """Save equity data to the exch_us_equity.equity_data table with exact minute timestamps"""
        if not self.pool:
            logger.error("Cannot save equity data: database not connected")
            return False
            
        # Truncate timestamp to exact minute
        exact_minute_timestamp = self._truncate_to_minute(timestamp)
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    stmt = await conn.prepare('''
                        INSERT INTO exch_us_equity.equity_data(
                            timestamp, symbol, currency, open, high, low, close, 
                            vwap, vwas, vwav, volume, count
                        ) VALUES($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                        ON CONFLICT (timestamp, symbol) DO UPDATE SET
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            vwap = EXCLUDED.vwap,
                            vwas = EXCLUDED.vwas,
                            vwav = EXCLUDED.vwav,
                            volume = EXCLUDED.volume,
                            count = EXCLUDED.count
                    ''')
                    
                    records = [
                        (
                            exact_minute_timestamp,  # Use truncated timestamp
                            eq['symbol'],
                            eq['currency'],
                            float(eq['open']),
                            float(eq['high']),
                            float(eq['low']),
                            float(eq['close']),
                            float(eq['vwap']),
                            float(eq['vwas']),
                            float(eq['vwav']),
                            int(eq['volume']),
                            int(eq['trade_count'])
                        )
                        for eq in equity_data
                    ]
                    
                    await stmt.executemany(records)
                    
                logger.info(f"Saved {len(equity_data)} equity records to database with exact minute timestamp: {exact_minute_timestamp}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving equity data to database: {e}")
            return False

    async def save_fx_data(self, fx_data: List[Dict[str, Any]], timestamp: datetime):
        """Save FX data to the exch_us_equity.fx_data table with exact minute timestamps"""
        if not self.pool:
            logger.error("Cannot save FX data: database not connected")
            return False
            
        # Truncate timestamp to exact minute
        exact_minute_timestamp = self._truncate_to_minute(timestamp)
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    stmt = await conn.prepare('''
                        INSERT INTO exch_us_equity.fx_data(
                            timestamp, from_currency, to_currency, rate
                        ) VALUES($1, $2, $3, $4)
                        ON CONFLICT (timestamp, from_currency, to_currency) DO UPDATE SET
                            rate = EXCLUDED.rate
                    ''')
                    
                    records = [
                        (
                            exact_minute_timestamp,  # Use truncated timestamp
                            fx['from_currency'],
                            fx['to_currency'],
                            float(fx['rate'])
                        )
                        for fx in fx_data
                    ]
                    
                    await stmt.executemany(records)
                    
                logger.info(f"Saved {len(fx_data)} FX records to database with exact minute timestamp: {exact_minute_timestamp}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving FX data to database: {e}")
            return False