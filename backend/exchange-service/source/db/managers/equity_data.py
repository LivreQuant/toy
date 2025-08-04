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
                    # Convert timestamp string to actual datetime object - EXACT MATCHING
                    from datetime import datetime
                    
                    if len(timestamp_str) >= 13 and '_' in timestamp_str:
                        date_part = timestamp_str[:8]  # "20250804"
                        time_part = timestamp_str[9:]  # "0313"
                        formatted_date = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"  # "2025-08-04"
                        formatted_time = f"{time_part[:2]}:{time_part[2:]}:00"  # "03:13:00"
                        timestamp_string = f"{formatted_date} {formatted_time}+00"
                        
                        # Convert to actual datetime object
                        target_datetime = datetime.fromisoformat(timestamp_string.replace('+00', '+00:00'))
                        conditions.append(f"timestamp = ${param_count}")  # EXACT MATCH, NOT LIKE
                        params.append(target_datetime)

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

                self.logger.info(f"✅ Loaded equity data: {len(equity_data)} records for timestamp: {timestamp_str}")
                return equity_data

        except Exception as e:
            self.logger.error(f"❌ Error loading equity data for {timestamp_str}: {e}")
            import traceback
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return []