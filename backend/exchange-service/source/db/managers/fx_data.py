# source/db/managers/fx_data.py
from datetime import datetime
from typing import Dict, List
from source.db.managers.base_manager import BaseTableManager


class FxDataManager(BaseTableManager):
    """Manager for fx data table"""

    # In source/db/managers/fx_data.py
    async def load_fx_data(self, timestamp_str: str = None, from_currency: str = None, to_currency: str = None) -> List[
        Dict]:
        """Load FX data from PostgreSQL"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
                target_datetime = self._get_timestamp_str(timestamp_str)

                query = f"""
                    SELECT timestamp, from_currency, to_currency, rate
                    FROM exch_us_equity.fx_data 
                    WHERE timestamp = $1
                """

                rows = await conn.fetch(query, target_datetime)
                print(rows)

                fx_data = []
                for row in rows:
                    fx_data.append({
                        'timestamp': row['timestamp'],
                        'from_currency': row['from_currency'],
                        'to_currency': row['to_currency'],
                        'rate': row['rate']
                    })

                self.logger.info(f"✅ Loaded FX data: {len(fx_data)} records")
                return fx_data

        except Exception as e:
            self.logger.error(f"❌ Error loading FX data: {e}")
            return []
