# source/db/managers/return_data.py
from typing import Dict, List
from datetime import datetime
import traceback
from decimal import Decimal
import uuid
from source.db.managers.base_manager import BaseTableManager


class ReturnDataManager(BaseTableManager):
    """Manager for return data table operations"""

    async def load_book_data(self, book_id: str, timestamp_str: str) -> List[Dict]:
        """Load book returns data from PostgreSQL using normalized schema"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
                target_datetime = self._get_timestamp_str(timestamp_str)

                query = """
                    SELECT book_id, timestamp, return_id, category, subcategory,
                        emv, bmv, bmv_book, cf, periodic_return_subcategory,
                        cumulative_return_subcategory, contribution_percentage,
                        periodic_return_contribution, cumulative_return_contribution
                    FROM exch_us_equity.return_data 
                    WHERE book_id = $1 AND timestamp = $2
                """

                rows = await conn.fetch(query, book_id, target_datetime)

                returns_data = []
                for row in rows:
                    returns_data.append({
                        'book_id': row['book_id'],
                        'timestamp': row['timestamp'],
                        'return_id': row['return_id'],
                        'category': row['category'],
                        'subcategory': row['subcategory'],
                        'emv': float(row['emv']),
                        'bmv': float(row['bmv']),
                        'bmv_book': float(row['bmv_book']),
                        'cf': float(row['cf']),
                        'periodic_return_subcategory': float(row['periodic_return_subcategory']),
                        'cumulative_return_subcategory': float(row['cumulative_return_subcategory']),
                        'contribution_percentage': float(row['contribution_percentage']),
                        'periodic_return_contribution': float(row['periodic_return_contribution']),
                        'cumulative_return_contribution': float(row['cumulative_return_contribution'])
                    })

                self.logger.info(f"✅ Loaded return data: {len(returns_data)} records for timestamp: {timestamp_str}")
                return returns_data

        except Exception as e:
            self.logger.error(f"❌ Error loading return data for {timestamp_str}: {e}")
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return []

    async def insert_simulation_data(self, data: List[Dict], book_id: str, timestamp: datetime) -> int:
        """Insert return simulation data into normalized table"""
        await self.ensure_connection()

        if not data:
            return 0

        try:
            async with self.pool.acquire() as conn:
                query = """
                    INSERT INTO exch_us_equity.return_data (
                        book_id, timestamp, return_id, category, subcategory,
                        emv, bmv, bmv_book, cf, periodic_return_subcategory,
                        cumulative_return_subcategory, contribution_percentage,
                        periodic_return_contribution, cumulative_return_contribution
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                    ON CONFLICT (book_id, timestamp, return_id) DO UPDATE SET
                        category = EXCLUDED.category,
                        subcategory = EXCLUDED.subcategory,
                        emv = EXCLUDED.emv,
                        bmv = EXCLUDED.bmv,
                        bmv_book = EXCLUDED.bmv_book,
                        cf = EXCLUDED.cf,
                        periodic_return_subcategory = EXCLUDED.periodic_return_subcategory,
                        cumulative_return_subcategory = EXCLUDED.cumulative_return_subcategory,
                        contribution_percentage = EXCLUDED.contribution_percentage,
                        periodic_return_contribution = EXCLUDED.periodic_return_contribution,
                        cumulative_return_contribution = EXCLUDED.cumulative_return_contribution
                """

                records = []
                for record in data:
                    records.append((
                        book_id,
                        timestamp,
                        record.get('return_id', f"RET_{uuid.uuid4().hex[:8]}"),
                        record.get('category', 'TOTAL'),
                        record.get('subcategory', 'PORTFOLIO'),
                        Decimal(str(record.get('emv', 0))),
                        Decimal(str(record.get('bmv', 0))),
                        Decimal(str(record.get('bmv_book', 0))),
                        Decimal(str(record.get('cf', 0))),
                        Decimal(str(record.get('periodic_return_subcategory', 0))),
                        Decimal(str(record.get('cumulative_return_subcategory', 0))),
                        Decimal(str(record.get('contribution_percentage', 0))),
                        Decimal(str(record.get('periodic_return_contribution', 0))),
                        Decimal(str(record.get('cumulative_return_contribution', 0)))
                    ))

                await conn.executemany(query, records)

                self.logger.info(f"✅ Inserted {len(records)} return records for {book_id}")
                return len(records)

        except Exception as e:
            self.logger.error(f"❌ Error inserting return simulation data: {e}")
            return 0
