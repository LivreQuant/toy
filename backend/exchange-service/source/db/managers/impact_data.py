# source/db/managers/impact_data.py
from typing import Dict, List
from datetime import datetime
import traceback
from decimal import Decimal
from source.simulation.managers.impact import ImpactState
from source.db.managers.base_manager import BaseTableManager


class ImpactDataManager(BaseTableManager):
    """Manager for impact data table"""

    async def load_book_data(self, book_id: str, timestamp_str: str) -> Dict[str, ImpactState]:
        """Load book impact data from PostgreSQL"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
                target_datetime = self._get_timestamp_str(timestamp_str)

                query = """
                    SELECT book_id, timestamp, symbol, trade_id, previous_impact,
                        current_impact, currency, base_price, impacted_price, cumulative_volume,
                        trade_volume, start_timestamp, end_timestamp, impact_type
                    FROM exch_us_equity.impact_data 
                    WHERE book_id = $1 AND timestamp = $2
                """

                rows = await conn.fetch(query, book_id, target_datetime)

                impact_data = {}
                for row in rows:
                    symbol = row['symbol']
                    impact_data[symbol] = ImpactState(
                        symbol=symbol,
                        trade_id=row['trade_id'],
                        previous_impact=Decimal(row['previous_impact']),
                        current_impact=Decimal(row['current_impact']),
                        currency=row['currency'],
                        base_price=Decimal(row['base_price']),
                        impacted_price=Decimal(row['impacted_price']),
                        cumulative_volume=int(row['cumulative_volume']),
                        trade_volume=int(row['trade_volume']),
                        start_timestamp=row['start_timestamp'],
                        end_timestamp=row['end_timestamp'],
                        impact_type=row['impact_type']
                    )

                self.logger.info(f"✅ Loaded impact data: {len(impact_data)} records for timestamp: {timestamp_str}")
                return impact_data

        except Exception as e:
            self.logger.error(f"❌ Error loading impact data for {timestamp_str}: {e}")
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return {}

    async def insert_simulation_data(self, data: List[Dict], book_id: str, timestamp: datetime) -> int:
        """Insert impact simulation data"""
        await self.ensure_connection()

        if not data:
            return 0

        try:
            async with self.pool.acquire() as conn:
                query = """
                    INSERT INTO exch_us_equity.impact_data (
                        book_id, timestamp, symbol, trade_id, previous_impact,
                        current_impact, currency, base_price, impacted_price, cumulative_volume,
                        trade_volume, start_timestamp, end_timestamp, impact_type
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """

                records = []
                for record in data:
                    if record.get('previous_impact', 0) == 0 and record.get('current_impact', 0) == 0:
                        continue
                    records.append((
                        book_id,
                        timestamp,
                        record['symbol'],
                        record.get('trade_id', ''),
                        Decimal(str(record.get('previous_impact', 0))),
                        Decimal(str(record.get('current_impact', 0))),
                        record.get('currency', 'USD'),
                        Decimal(str(record.get('base_price', 0))),
                        Decimal(str(record.get('impacted_price', 0))),
                        Decimal(str(record.get('cumulative_volume', 0))),
                        Decimal(str(record.get('trade_volume', 0))),
                        datetime.fromisoformat(record.get('start_timestamp')) if record.get('start_timestamp') else None,
                        datetime.fromisoformat(record.get('end_timestamp')) if record.get('end_timestamp') else None,
                        record.get('impact_type', '')
                    ))

                if not records:
                    return 0

                await conn.executemany(query, records)

                self.logger.info(f"✅ Inserted {len(records)} impact records for {book_id}")
                return len(records)

        except Exception as e:
            self.logger.error(f"❌ Error inserting impact data: {e}")
            return 0
