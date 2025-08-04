# source/db/managers/impact_data.py
from typing import Dict, List
from datetime import datetime
from decimal import Decimal
from source.simulation.managers.impact import ImpactState
from source.db.managers.base_manager import BaseTableManager


class ImpactDataManager(BaseTableManager):
    """Manager for impact data table"""

    async def load_user_data(self, user_id: str, timestamp_str: str) -> Dict[str, ImpactState]:
        """Load user impact data from PostgreSQL"""
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
                    SELECT user_id, timestamp, symbol, trade_id, previous_impact,
                        current_impact, currency, base_price, impacted_price, cumulative_volume,
                        trade_volume, start_timestamp, end_timestamp, impact_type
                    FROM exch_us_equity.impact_data 
                    WHERE user_id = $1 AND timestamp = $2
                """

                rows = await conn.fetch(query, user_id, target_datetime)

                impact_data = {}
                for row in rows:
                    symbol = row['symbol']
                    impact_data[symbol] = ImpactState(
                        symbol=symbol,
                        previous_impact=float(row['previous_impact']),
                        current_impact=float(row['current_impact']),
                        currency=row['currency'],
                        base_price=float(row['base_price']),
                        impacted_price=float(row['impacted_price']),
                        cumulative_volume=float(row['cumulative_volume']),
                        trade_volume=float(row['trade_volume']),
                        start_timestamp=row['start_timestamp'],
                        end_timestamp=row['end_timestamp'],
                        impact_type=row['impact_type']
                    )

                self.logger.info(f"✅ Loaded impact data: {len(impact_data)} records for timestamp: {timestamp_str}")
                return impact_data

        except Exception as e:
            self.logger.error(f"❌ Error loading impact data for {timestamp_str}: {e}")
            import traceback
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return {}

    async def insert_simulation_data(self, data: List[Dict], user_id: str, timestamp: datetime) -> int:
        """Insert impact simulation data"""
        await self.ensure_connection()

        if not data:
            return 0

        try:
            async with self.pool.acquire() as conn:
                query = """
                    INSERT INTO exch_us_equity.impact_data (
                        user_id, timestamp, symbol, trade_id, previous_impact,
                        current_impact, currency, base_price, impacted_price, cumulative_volume,
                        trade_volume, start_timestamp, end_timestamp, impact_type
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """

                import uuid
                records = []
                for record in data:
                    if record.get('previous_impact', 0) == 0 and record.get('current_impact', 0) == 0:
                        continue
                    records.append((
                        user_id,
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

                self.logger.info(f"✅ Inserted {len(records)} impact records for {user_id}")
                return len(records)

        except Exception as e:
            self.logger.error(f"❌ Error inserting impact data: {e}")
            return 0
