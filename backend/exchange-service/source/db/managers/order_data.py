# source/db/managers/order_data.py
from typing import Dict, List
from datetime import datetime
from decimal import Decimal
from source.db.managers.base_manager import BaseTableManager


class OrderDataManager(BaseTableManager):
    """Manager for order data table"""

    async def load_user_data(self, user_id: str, timestamp_str: str) -> List[Dict]:
        """Load user orders data from PostgreSQL"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT order_pk, user_id, timestamp, order_id, cl_order_id, symbol, side,
                           original_qty, remaining_qty, completed_qty, currency, price,
                           order_type, participation_rate, order_state, submit_timestamp,
                           start_timestamp, tag, conviction_id
                    FROM exch_us_equity.order_data 
                    WHERE user_id = $1 AND timestamp::text LIKE $2
                """

                rows = await conn.fetch(query, user_id, f"{timestamp_str}%")

                orders_data = []
                for row in rows:
                    orders_data.append({
                        'order_pk': str(row['order_pk']),
                        'user_id': row['user_id'],
                        'timestamp': row['timestamp'],
                        'order_id': row['order_id'],
                        'cl_order_id': row['cl_order_id'],
                        'symbol': row['symbol'],
                        'side': row['side'],
                        'original_qty': row['original_qty'],
                        'remaining_qty': row['remaining_qty'],
                        'completed_qty': row['completed_qty'],
                        'currency': row['currency'],
                        'price': row['price'],
                        'order_type': row['order_type'],
                        'participation_rate': row['participation_rate'],
                        'order_state': row['order_state'],
                        'submit_timestamp': row['submit_timestamp'],
                        'start_timestamp': row['start_timestamp'],
                        'tag': row['tag'],
                        'conviction_id': row['conviction_id']
                    })

                self.logger.info(f"✅ Loaded orders data for {user_id}: {len(orders_data)} orders")
                return orders_data

        except Exception as e:
            self.logger.error(f"❌ Error loading orders data for {user_id}: {e}")
            return []

    async def insert_simulation_data(self, data: List[Dict], user_id: str, timestamp: datetime) -> int:
        """Insert order simulation data"""
        await self.ensure_connection()

        if not data:
            return 0

        try:
            async with self.pool.acquire() as conn:
                query = """
                    INSERT INTO exch_us_equity.order_data (
                        order_pk, user_id, timestamp, order_id, cl_order_id, symbol, side,
                        original_qty, remaining_qty, completed_qty, currency, price,
                        order_type, participation_rate, order_state, submit_timestamp,
                        start_timestamp, tag, conviction_id
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
                """

                import uuid
                records = []
                for record in data:
                    records.append((
                        uuid.uuid4(),
                        user_id,
                        timestamp,
                        record.get('order_id', ''),
                        record.get('cl_order_id', ''),
                        record['symbol'],
                        record.get('side', ''),
                        Decimal(str(record.get('original_qty', 0))),
                        Decimal(str(record.get('remaining_qty', 0))),
                        Decimal(str(record.get('completed_qty', 0))),
                        record.get('currency', 'USD'),
                        Decimal(str(record.get('price', 0))),
                        record.get('order_type', ''),
                        record.get('participation_rate', ''),
                        record.get('order_state', ''),
                        record.get('submit_timestamp'),
                        record.get('start_timestamp'),
                        record.get('tag'),
                        record.get('conviction_id')
                    ))

                await conn.executemany(query, records)

                self.logger.info(f"✅ Inserted {len(records)} order records for {user_id}")
                return len(records)

        except Exception as e:
            self.logger.error(f"❌ Error inserting order data: {e}")
            return 0
