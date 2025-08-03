# source/db/managers/equity_data.py
from typing import Dict, List
from source.db.managers.base_manager import BaseTableManager


class EquityDataManager(BaseTableManager):
    """Manager for equity data table"""

    async def load_equity_data(self, timestamp_str: str = None, symbol: str = None) -> List[Dict]:
        """Load equity data from PostgreSQL"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
                conditions = []
                params = []
                param_count = 0

                if timestamp_str:
                    param_count += 1
                    conditions.append(f"timestamp::text LIKE ${param_count}")
                    params.append(f"{timestamp_str}%")

                if symbol:
                    param_count += 1
                    conditions.append(f"symbol = ${param_count}")
                    params.append(symbol)

                where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

                query = f"""
                    SELECT timestamp, symbol, currency, open, high, low, close,
                           vwap, vwas, vwav, volume, count
                    FROM exch_us_equity.equity_data 
                    {where_clause}
                """

                rows = await conn.fetch(query, *params)

                equity_data = []
                for row in rows:
                    equity_data.append({
                        'timestamp': row['timestamp'],
                        'symbol': row['symbol'],
                        'currency': row['currency'],
                        'open': row['open'],
                        'high': row['high'],
                        'low': row['low'],
                        'close': row['close'],
                        'vwap': row['vwap'],
                        'vwas': row['vwas'],
                        'vwav': row['vwav'],
                        'volume': row['volume'],
                        'count': row['count']
                    })

                self.logger.info(f"✅ Loaded equity data: {len(equity_data)} records")
                return equity_data

        except Exception as e:
            self.logger.error(f"❌ Error loading equity data: {e}")
            return []
