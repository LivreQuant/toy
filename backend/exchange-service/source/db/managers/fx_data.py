# source/db/managers/fx_data.py
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
                conditions = []
                params = []
                param_count = 0

                if timestamp_str:
                    param_count += 1
                    # Convert timestamp string to actual datetime object
                    from datetime import datetime

                    if len(timestamp_str) >= 13 and '_' in timestamp_str:
                        date_part = timestamp_str[:8]  # "20240109"
                        time_part = timestamp_str[9:]  # "1932"
                        formatted_date = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"  # "2024-01-09"
                        formatted_time = f"{time_part[:2]}:{time_part[2:]}:00"  # "19:32:00"
                        timestamp_string = f"{formatted_date} {formatted_time}+00"

                        # Convert to actual datetime object
                        target_datetime = datetime.fromisoformat(timestamp_string.replace('+00', '+00:00'))
                        conditions.append(f"timestamp = ${param_count}")
                        params.append(target_datetime)
                    else:
                        # Parse the timestamp string to datetime
                        target_datetime = datetime.fromisoformat(timestamp_str)
                        conditions.append(f"timestamp = ${param_count}")
                        params.append(target_datetime)

                if from_currency:
                    param_count += 1
                    conditions.append(f"from_currency = ${param_count}")
                    params.append(from_currency)

                if to_currency:
                    param_count += 1
                    conditions.append(f"to_currency = ${param_count}")
                    params.append(to_currency)

                where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

                query = f"""
                    SELECT fx_id, timestamp, from_currency, to_currency, rate
                    FROM exch_us_equity.fx_data 
                    {where_clause}
                """

                rows = await conn.fetch(query, *params)
                print(rows)

                fx_data = []
                for row in rows:
                    fx_data.append({
                        'fx_id': str(row['fx_id']),
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
