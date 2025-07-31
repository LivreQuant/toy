# source/db/managers/risk_factor_data.py
from typing import Dict, List
from source.db.managers.base_manager import BaseTableManager


class RiskFactorDataManager(BaseTableManager):
    """Manager for risk factor data table operations"""

    async def load_user_data(self, timestamp_str: str = None) -> List[Dict]:
        """Load risk factor data from PostgreSQL using date field"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
                if timestamp_str:
                    # Convert timestamp_str to date object
                    if len(timestamp_str) >= 8 and '_' not in timestamp_str:
                        # Format: "20240109" -> "2024-01-09"
                        date_str = f"{timestamp_str[:4]}-{timestamp_str[4:6]}-{timestamp_str[6:8]}"
                    elif len(timestamp_str) >= 8:
                        # Format: "20240109_1932" -> "2024-01-09"
                        date_part = timestamp_str[:8]
                        date_str = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
                    else:
                        date_str = timestamp_str

                    # Convert to date object
                    from datetime import datetime
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

                    query = """
                        SELECT risk_id, date, symbol, type, name, value
                        FROM exch_us_equity.risk_factor_data 
                        WHERE date = $1
                        ORDER BY symbol ASC, type ASC, name ASC
                    """
                    rows = await conn.fetch(query, date_obj)
                else:
                    query = """
                        SELECT risk_id, date, symbol, type, name, value
                        FROM exch_us_equity.risk_factor_data 
                        ORDER BY date DESC, symbol ASC, type ASC, name ASC
                        LIMIT 1000
                    """
                    rows = await conn.fetch(query)

                risk_factor_data = []
                for row in rows:
                    risk_factor_data.append({
                        'risk_id': str(row['risk_id']),
                        'date': row['date'],
                        'symbol': row['symbol'],
                        'type': row['type'],
                        'name': row['name'],
                        'value': row['value'],
                    })

                self.logger.info(f"✅ Loaded risk factor data: {len(risk_factor_data)} records")
                return risk_factor_data

        except Exception as e:
            self.logger.error(f"❌ Error loading risk factor data: {e}")
            return []