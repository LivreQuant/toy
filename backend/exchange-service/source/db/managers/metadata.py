# source/db/managers/metadata.py
import json
from typing import Dict
from source.db.managers.base_manager import BaseTableManager


class MetadataManager(BaseTableManager):
    """Manager for exchange metadata table"""

    async def load_exchange_metadata(self, exch_id: str = None) -> Dict:
        """Load exchange metadata from PostgreSQL"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
                if exch_id:
                    query = """
                        SELECT exch_id, exchange_type, timezone, exchanges, 
                               last_snap, pre_market_open, market_open, market_close, 
                               post_market_close, updated_time
                        FROM exch_us_equity.metadata 
                        WHERE exch_id = $1
                        ORDER BY updated_time DESC
                        LIMIT 1
                    """
                    row = await conn.fetchrow(query, exch_id)
                else:
                    query = """
                        SELECT exch_id, exchange_type, timezone, exchanges, 
                               last_snap, pre_market_open, market_open, market_close, 
                               post_market_close, updated_time
                        FROM exch_us_equity.metadata 
                        ORDER BY updated_time DESC
                        LIMIT 1
                    """
                    row = await conn.fetchrow(query)

                if row:
                    metadata = {
                        'exch_id': str(row['exch_id']),
                        'exchange_type': row['exchange_type'],
                        'timezone': row['timezone'],
                        'exchanges': row['exchanges'],
                        'last_snap': row['last_snap'],
                        'pre_market_open': row['pre_market_open'],
                        'market_open': row['market_open'],
                        'market_close': row['market_close'],
                        'post_market_close': row['post_market_close'],
                        'updated_time': row['updated_time']
                    }

                    self.logger.info(f"✅ Loaded exchange metadata for exch_id: {exch_id}")
                    return metadata
                else:
                    self.logger.warning(f"⚠️ No exchange metadata found for exch_id: {exch_id}")
                    return {}

        except Exception as e:
            self.logger.error(f"❌ Error loading exchange metadata: {e}")
            return {}

    async def update_exchange_metadata(self, metadata: Dict) -> bool:
        """Insert exchange metadata"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
                query = """
                    INSERT INTO exch_us_equity.metadata (
                        exch_id, exchange_type, timezone, exchanges, 
                        last_snap, pre_market_open, market_open, market_close, 
                        post_market_close
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (exch_id) DO UPDATE SET
                        exchange_type = EXCLUDED.exchange_type,
                        timezone = EXCLUDED.timezone,
                        exchanges = EXCLUDED.exchanges,
                        last_snap = EXCLUDED.last_snap,
                        pre_market_open = EXCLUDED.pre_market_open,
                        market_open = EXCLUDED.market_open,
                        market_close = EXCLUDED.market_close,
                        post_market_close = EXCLUDED.post_market_close,
                        updated_time = CURRENT_TIMESTAMP
                """

                await conn.execute(
                    query,
                    metadata['exch_id'],
                    metadata['exchange_type'],
                    metadata['timezone'],
                    metadata['exchanges'],
                    metadata['last_snap'],
                    metadata['pre_market_open'],
                    metadata['market_open'],
                    metadata['market_close'],
                    metadata['post_market_close']
                )

                self.logger.info(f"✅ Inserted/updated exchange metadata for exch_id: {metadata['exch_id']}")
                return True

        except Exception as e:
            self.logger.error(f"❌ Error inserting exchange metadata: {e}")
            return False