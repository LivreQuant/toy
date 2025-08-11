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
                # Convert timestamp string to actual datetime object - EXACT MATCHING
                from datetime import datetime
                
                if len(timestamp_str) >= 13 and '_' in timestamp_str:
                    date_part = timestamp_str[:8]  # "20250804"  
                    time_part = timestamp_str[9:]  # "0313"
                    formatted_date = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
                    formatted_time = f"{time_part[:2]}:{time_part[2:]}:00"
                    timestamp_string = f"{formatted_date} {formatted_time}+00"
                    target_datetime = datetime.fromisoformat(timestamp_string.replace('+00', '+00:00'))
                else:
                    target_datetime = datetime.fromisoformat(timestamp_str)

                query = """
                    SELECT user_id, timestamp, order_id, cl_order_id, symbol, side,
                        original_qty, remaining_qty, completed_qty, currency, price,
                        order_type, participation_rate, order_state, submit_timestamp,
                        start_timestamp, tag, conviction_id
                    FROM exch_us_equity.order_data 
                    WHERE user_id = $1 AND timestamp = $2
                """

                rows = await conn.fetch(query, user_id, target_datetime)

                orders_data = []
                for row in rows:
                    orders_data.append({
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

                self.logger.info(f"✅ Loaded order data: {len(orders_data)} records for timestamp: {timestamp_str}")
                return orders_data

        except Exception as e:
            self.logger.error(f"❌ Error loading order data for {timestamp_str}: {e}")
            import traceback
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return []

    async def insert_simulation_data(self, data: List[Dict], user_id: str, timestamp: datetime) -> int:
        """Insert order simulation data"""
        if not data:
            return 0

        try:
            async with self.pool.acquire() as conn:
                query = """
                    INSERT INTO exch_us_equity.order_data (
                        user_id, timestamp, order_id, cl_order_id, symbol, side,
                        original_qty, remaining_qty, completed_qty, currency, price,
                        order_type, participation_rate, order_state, submit_timestamp,
                        start_timestamp, tag, conviction_id
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                """

                records = []
                for record in data:
                    records.append((
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
