# source/db/managers/return_data.py
from typing import Dict, List
from datetime import datetime
from decimal import Decimal
from source.db.managers.base_manager import BaseTableManager


class ReturnDataManager(BaseTableManager):
    """Manager for return data table operations"""

    async def load_user_data(self, user_id: str, timestamp_str: str) -> List[Dict]:
        """Load user returns data from PostgreSQL using normalized schema"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT return_pk, user_id, timestamp, return_id, category, subcategory,
                           emv, bmv, bmv_book, cf, periodic_return_subcategory,
                           cumulative_return_subcategory, contribution_percentage,
                           periodic_return_contribution, cumulative_return_contribution
                    FROM exch_us_equity.return_data 
                    WHERE user_id = $1 AND timestamp::text LIKE $2
                """

                rows = await conn.fetch(query, user_id, f"{timestamp_str}%")

                returns_data = []
                for row in rows:
                    returns_data.append({
                        'return_pk': str(row['return_pk']),
                        'user_id': row['user_id'],
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

                self.logger.info(f"✅ Loaded returns data for {user_id}: {len(returns_data)} returns")
                return returns_data

        except Exception as e:
            self.logger.error(f"❌ Error loading returns data for {user_id}: {e}")
            return []

    async def insert_simulation_data(self, data: List[Dict], user_id: str, timestamp: datetime) -> int:
        """Insert return simulation data into normalized table"""
        await self.ensure_connection()

        if not data:
            return 0

        try:
            async with self.pool.acquire() as conn:
                query = """
                    INSERT INTO exch_us_equity.return_data (
                        return_pk, user_id, timestamp, return_id, category, subcategory,
                        emv, bmv, bmv_book, cf, periodic_return_subcategory,
                        cumulative_return_subcategory, contribution_percentage,
                        periodic_return_contribution, cumulative_return_contribution
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                    ON CONFLICT (user_id, timestamp, return_id) DO UPDATE SET
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

                import uuid
                records = []
                for record in data:
                    records.append((
                        uuid.uuid4(),
                        user_id,
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

                self.logger.info(f"✅ Inserted {len(records)} return records for {user_id}")
                return len(records)

        except Exception as e:
            self.logger.error(f"❌ Error inserting return simulation data: {e}")
            return 0
