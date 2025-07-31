# source/db/managers/account_data.py
from typing import Dict, List
from datetime import datetime
from decimal import Decimal
from source.simulation.managers.account import AccountBalance
from source.db.managers.base_manager import BaseTableManager


class AccountDataManager(BaseTableManager):
    """Manager for account data table"""

    async def load_user_data(self, user_id: str, timestamp_str: str) -> Dict[str, Dict[str, AccountBalance]]:
        """Load user account data from PostgreSQL"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
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
                else:
                    target_datetime = datetime.fromisoformat(timestamp_str)

                query = """
                    SELECT account_id, user_id, timestamp, type, currency, amount, 
                           previous_amount, change
                    FROM exch_us_equity.account_data 
                    WHERE user_id = $1 AND timestamp = $2
                """

                rows = await conn.fetch(query, user_id, target_datetime)

                # Initialize account structure
                from source.simulation.managers.account import AccountManager
                accounts = {balance_type: {} for balance_type in AccountManager.VALID_TYPES}

                for row in rows:
                    balance_type = row['type']
                    currency = row['currency']
                    amount = row['amount']

                    if balance_type in accounts:
                        accounts[balance_type][currency] = AccountBalance(
                            currency=currency,
                            amount=amount
                        )

                total_balances = sum(len(balances) for balances in accounts.values())
                self.logger.info(f"✅ Loaded account data for {user_id}: {total_balances} balances")
                return accounts

        except Exception as e:
            self.logger.error(f"❌ Error loading account data for {user_id}: {e}")
            return {}

    async def insert_simulation_data(self, data: List[Dict], user_id: str, timestamp: datetime) -> int:
        """Insert account simulation data"""
        await self.ensure_connection()

        if not data:
            return 0

        try:
            async with self.pool.acquire() as conn:
                query = """
                    INSERT INTO exch_us_equity.account_data (
                        account_id, user_id, timestamp, type, currency, amount,
                        previous_amount, change
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """

                import uuid
                records = []
                for record in data:
                    records.append((
                        uuid.uuid4(),
                        user_id,
                        timestamp,
                        record['type'],
                        record['currency'],
                        Decimal(str(record['amount'])),
                        Decimal(str(record.get('previous_amount', 0))),
                        Decimal(str(record.get('change', 0)))
                    ))

                await conn.executemany(query, records)

                self.logger.info(f"✅ Inserted {len(records)} account records for {user_id}")
                return len(records)

        except Exception as e:
            self.logger.error(f"❌ Error inserting account data: {e}")
            return 0
