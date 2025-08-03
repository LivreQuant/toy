# source/db/managers/cash_flow_data.py
import logging
import uuid
from typing import List, Dict
from datetime import datetime
from decimal import Decimal
from source.db.managers.base_manager import BaseTableManager


class CashFlowDataManager(BaseTableManager):
    """Manages cash flow data table operations"""

    def __init__(self, db_manager):
        super().__init__(db_manager)
        self.logger = logging.getLogger(self.__class__.__name__)

    async def load_user_data(self, user_id: str, timestamp_str: str):
        """Load user cash flow data from the database"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT user_id, timestamp, flow_type, from_account, from_currency,
                           from_fx, from_amount, to_account, to_currency, to_fx, to_amount,
                           instrument, trade_id, description
                    FROM exch_us_equity.cash_flow_data
                    WHERE user_id = $1 AND timestamp = $2
                    ORDER BY timestamp ASC
                """

                rows = await conn.fetch(query, user_id, timestamp_str)

                cash_flow_data = []
                for row in rows:
                    cash_flow_data.append({
                        'user_id': row['user_id'],
                        'timestamp': row['timestamp'],
                        'flow_type': row['flow_type'],
                        'from_account': row['from_account'],
                        'from_currency': row['from_currency'],
                        'from_fx': float(row['from_fx']),
                        'from_amount': float(row['from_amount']),
                        'to_account': row['to_account'],
                        'to_currency': row['to_currency'],
                        'to_fx': float(row['to_fx']),
                        'to_amount': float(row['to_amount']),
                        'instrument': row['instrument'],
                        'trade_id': row['trade_id'],
                        'description': row['description']
                    })

                self.logger.info(f"✅ Loaded cash flow data for {user_id}: {len(cash_flow_data)} flows")
                return cash_flow_data

        except Exception as e:
            self.logger.error(f"❌ Error loading cash flow data for {user_id}: {e}")
            return []

    async def insert_simulation_data(self, data: List[Dict], user_id: str, timestamp: datetime) -> int:
        """Insert cash flow simulation data"""
        await self.ensure_connection()

        self.logger.info(f"Attempting to insert {len(data)} cash flow records for user {user_id} at timestamp {timestamp}")
        if not data:
            self.logger.info(f"No cash flow data provided for user {user_id} at timestamp {timestamp}. Skipping insertion.")
            return 0

        try:
            async with self.pool.acquire() as conn:
                query = """
                    INSERT INTO exch_us_equity.cash_flow_data (
                        user_id, timestamp, flow_type, from_account, from_currency,
                        from_fx, from_amount, to_account, to_currency, to_fx, to_amount,
                        instrument, trade_id, description
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                    ON CONFLICT (user_id, timestamp, flow_type, from_account, to_account, trade_id) 
                    DO UPDATE SET
                        from_currency = EXCLUDED.from_currency,
                        from_fx = EXCLUDED.from_fx,
                        from_amount = EXCLUDED.from_amount,
                        to_currency = EXCLUDED.to_currency,
                        to_fx = EXCLUDED.to_fx,
                        to_amount = EXCLUDED.to_amount,
                        instrument = EXCLUDED.instrument,
                        description = EXCLUDED.description
                """

                records = []
                for record in data:
                    records.append((
                        user_id,
                        timestamp,
                        record.get('flow_type', ''),
                        record.get('from_account', ''),
                        record.get('from_currency', 'USD'),
                        Decimal(str(record.get('from_fx', 1.0))),
                        Decimal(str(record.get('from_amount', 0))),
                        record.get('to_account', ''),
                        record.get('to_currency', 'USD'),
                        Decimal(str(record.get('to_fx', 1.0))),
                        Decimal(str(record.get('to_amount', 0))),
                        record.get('instrument', None),
                        record.get('trade_id', None),
                        record.get('description', None)
                    ))

                await conn.executemany(query, records)

                self.logger.info(f"✅ Inserted {len(records)} cash flow records for {user_id}")
                return len(records)

        except Exception as e:
            self.logger.error(f"❌ Error inserting cash flow simulation data: {e}")
            import traceback
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return 0