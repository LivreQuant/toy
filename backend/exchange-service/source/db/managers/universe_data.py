# source/db/managers/universe_data.py
from typing import Dict, List
import traceback
from datetime import datetime
from source.db.managers.base_manager import BaseTableManager


class UniverseDataManager(BaseTableManager):
    """Manager for universe data table operations"""

    async def load_universe_data(self, timestamp_str: str = None) -> List[Dict]:
        """Load universe data from PostgreSQL using date field"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
                target_datetime = self._get_timestamp_str(timestamp_str)
                target_date = target_datetime.date()

                query = f"""
                    SELECT date, symbol, sector, industry,
                           market_cap, country, currency, avg_daily_volume, beta,
                           primary_exchange, shares_outstanding
                    FROM exch_us_equity.universe_data 
                    WHERE date = $1
                """

                rows = await conn.fetch(query, target_date)

                universe_data = []
                for row in rows:
                    universe_data.append({
                        'date': row['date'],
                        'symbol': row['symbol'],
                        'sector': row['sector'],
                        'industry': row['industry'],
                        'market_cap': row['market_cap'],
                        'country': row['country'],
                        'currency': row['currency'],
                        'avg_daily_volume': row['avg_daily_volume'],
                        'beta': row['beta'],
                        'primary_exchange': row['primary_exchange'],
                        'shares_outstanding': row['shares_outstanding'],
                    })

                self.logger.info(f"✅ Loaded universe data: {len(universe_data)} symbols")
                return universe_data

        except Exception as e:
            self.logger.error(f"❌ Error loading universe data: {e}")
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return []
