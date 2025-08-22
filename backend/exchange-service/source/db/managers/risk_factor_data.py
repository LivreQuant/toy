# source/db/managers/risk_factor_data.py
from datetime import datetime
from typing import Dict, List
from source.db.managers.base_manager import BaseTableManager


class RiskFactorDataManager(BaseTableManager):
    """Manager for risk factor data table operations"""

    async def load_book_data(self, timestamp_str: str = None) -> List[Dict]:
        """Load risk factor data from PostgreSQL using date field"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
                target_datetime = self._get_timestamp_str(timestamp_str)
                target_date = target_datetime.date()

                query = """
                    SELECT date, symbol, type, name, value
                    FROM exch_us_equity.risk_factor_data 
                    WHERE date = $1
                """
                rows = await conn.fetch(query, target_date)

                risk_factor_data = []
                for row in rows:
                    risk_factor_data.append({
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