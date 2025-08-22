# source/db/managers/equity_data.py
import traceback
from datetime import datetime
from typing import Dict, List
from source.db.managers.base_manager import BaseTableManager


class EquityDataManager(BaseTableManager):
    """Manager for equity data table"""

    async def load_equity_data(self, timestamp_str: str = None) -> List[Dict]:
        """Load equity data from PostgreSQL"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
                target_datetime = self._get_timestamp_str(timestamp_str)

                query = f"""
                    SELECT timestamp, symbol, currency, open, high, low, close,
                        vwap, vwas, vwav, volume, count
                    FROM exch_us_equity.equity_data 
                    WHERE timestamp = $1
                """

                rows = await conn.fetch(query, target_datetime)

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

                self.logger.info(f"✅ Loaded equity data: {len(equity_data)} records for timestamp: {timestamp_str}")
                return equity_data

        except Exception as e:
            self.logger.error(f"❌ Error loading equity data for {timestamp_str}: {e}")
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return []