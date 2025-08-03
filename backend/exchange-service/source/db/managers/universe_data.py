# source/db/managers/universe_data.py
from typing import Dict, List
from datetime import datetime
from source.db.managers.base_manager import BaseTableManager


class UniverseDataManager(BaseTableManager):
    """Manager for universe data table operations"""

    async def load_universe_data(self, timestamp_str: str = None, symbol: str = None) -> List[Dict]:
        """Load universe data from PostgreSQL using date field"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
                conditions = []
                params = []
                param_count = 0

                if timestamp_str:
                    param_count += 1
                    # Convert timestamp_str to date - handle both formats
                    if len(timestamp_str) >= 8 and '_' not in timestamp_str:
                        # Format: "20240109" -> "2024-01-09"
                        date_str = f"{timestamp_str[:4]}-{timestamp_str[4:6]}-{timestamp_str[6:8]}"
                    elif len(timestamp_str) >= 8:
                        # Format: "20240109_1932" -> "2024-01-09"
                        date_part = timestamp_str[:8]
                        date_str = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
                    else:
                        # Already in YYYY-MM-DD format
                        date_str = timestamp_str

                    # Convert string to actual date object for PostgreSQL
                    from datetime import datetime
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                    conditions.append(f"date = ${param_count}")
                    params.append(date_obj)

                if symbol:
                    param_count += 1
                    conditions.append(f"symbol = ${param_count}")
                    params.append(symbol)

                where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

                query = f"""
                    SELECT date, symbol, sector, industry,
                           market_cap, country, currency, avg_daily_volume, beta,
                           primary_exchange, shares_outstanding
                    FROM exch_us_equity.universe_data 
                    {where_clause}
                    ORDER BY date DESC, symbol ASC
                """

                if not conditions:
                    query += " LIMIT 5000"

                rows = await conn.fetch(query, *params)

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
            import traceback
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return []
