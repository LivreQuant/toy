# source/db/managers/trade_data.py
from typing import Dict, List
from datetime import datetime
import traceback
import uuid
from decimal import Decimal
from source.db.managers.base_manager import BaseTableManager


class TradeDataManager(BaseTableManager):
    """Manager for trade data table operations"""

    async def load_book_data(self, book_id: str, timestamp_str: str) -> List[Dict]:
        """Load book trades data from PostgreSQL using normalized schema"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
                target_datetime = self._get_timestamp_str(timestamp_str)

                query = """
                    SELECT book_id, start_timestamp, end_timestamp, trade_id,
                           order_id, cl_order_id, symbol, side, currency, price,
                           quantity, detail
                    FROM exch_us_equity.trade_data 
                    WHERE book_id = $1 AND end_timestamp = $2
                """

                rows = await conn.fetch(query, book_id, target_datetime)

                trades_data = []
                for row in rows:
                    trades_data.append({
                        'book_id': row['book_id'],
                        'start_timestamp': row['start_timestamp'],
                        'end_timestamp': row['end_timestamp'],
                        'trade_id': row['trade_id'],
                        'order_id': row['order_id'],
                        'cl_order_id': row['cl_order_id'],
                        'symbol': row['symbol'],
                        'side': row['side'],
                        'currency': row['currency'],
                        'price': float(row['price']),
                        'quantity': float(row['quantity']),
                        'detail': row['detail']
                    })

                self.logger.info(f"✅ Loaded trades data for {book_id}: {len(trades_data)} trades")
                return trades_data

        except Exception as e:
            self.logger.error(f"❌ Error loading trades data for {book_id}: {e}")
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return []

    async def insert_simulation_data(self, data: List[Dict], book_id: str, timestamp: datetime) -> int:
        """Insert trade simulation data into normalized table"""
        await self.ensure_connection()

        if not data:
            return 0

        try:
            async with self.pool.acquire() as conn:
                # Insert into normalized trade_data table
                query = """
                    INSERT INTO exch_us_equity.trade_data (
                        book_id, start_timestamp, end_timestamp, trade_id,
                        order_id, cl_order_id, symbol, side, currency, price,
                        quantity, detail
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    ON CONFLICT (book_id, end_timestamp, trade_id) DO UPDATE SET
                        start_timestamp = EXCLUDED.start_timestamp,
                        order_id = EXCLUDED.order_id,
                        cl_order_id = EXCLUDED.cl_order_id,
                        symbol = EXCLUDED.symbol,
                        side = EXCLUDED.side,
                        currency = EXCLUDED.currency,
                        price = EXCLUDED.price,
                        quantity = EXCLUDED.quantity,
                        detail = EXCLUDED.detail
                """

                records = []
                for record in data:
                    records.append((
                        book_id,
                        record.get('start_timestamp', timestamp),
                        record.get('end_timestamp', timestamp),
                        record.get('trade_id', f"TRADE_{uuid.uuid4().hex[:8]}"),
                        record.get('order_id', ''),
                        record.get('cl_order_id', ''),
                        record['symbol'],
                        record.get('side', 'BUY'),
                        record.get('currency', 'USD'),
                        Decimal(str(record.get('price', 0))),
                        Decimal(str(record.get('quantity', 0))),
                        record.get('detail', '')
                    ))

                await conn.executemany(query, records)

                self.logger.info(f"✅ Inserted {len(records)} trade records for {book_id}")
                return len(records)

        except Exception as e:
            self.logger.error(f"❌ Error inserting trade simulation data: {e}")
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return 0
