# source/db/managers/metadata.py
from typing import Dict
from source.db.managers.base_manager import BaseTableManager


class MetadataManager(BaseTableManager):
    """Manager for exchange metadata table"""

    async def load_exchange_metadata(self, exch_id: str) -> Dict:
        """Load exchange metadata from PostgreSQL"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
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
        """Update only last_snap for existing exchange, or insert full metadata for new exchange"""
        await self.ensure_connection()
        try:
            async with self.pool.acquire() as conn:
                # First, try to update only last_snap for existing exchange
                update_query = """
                    UPDATE exch_us_equity.metadata 
                    SET last_snap = $2, 
                        updated_time = CURRENT_TIMESTAMP
                    WHERE exch_id = $1
                """
                
                result = await conn.execute(
                    update_query,
                    metadata['exch_id'],
                    metadata['last_snap']
                )
                
                # Check if the update affected any rows
                if result == "UPDATE 1":
                    self.logger.info(f"✅ Updated last_snap for existing exchange: {metadata['exch_id']}")
                    return True
                
                # If no rows were updated, this is a new exchange - do full insert
                insert_query = """
                    INSERT INTO exch_us_equity.metadata (
                        exch_id, exchange_type, timezone, exchanges,
                        last_snap, pre_market_open, market_open, market_close,
                        post_market_close, updated_time
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, CURRENT_TIMESTAMP)
                """
                
                await conn.execute(
                    insert_query,
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
                
                self.logger.info(f"✅ Inserted new exchange metadata for exch_id: {metadata['exch_id']}")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Error updating exchange metadata: {e}")
            return False