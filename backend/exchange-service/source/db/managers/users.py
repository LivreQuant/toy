# source/db/managers/users.py
from typing import Dict, List
from source.db.managers.base_manager import BaseTableManager


class UsersManager(BaseTableManager):
    """Manager for users table"""

    async def load_users_for_exchange(self, exch_id: str) -> List[Dict]:
        """Get all users for a specific exchange"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT user_id, exch_id, base_currency, timezone
                    FROM exch_us_equity.users 
                    WHERE exch_id = $1
                """
                rows = await conn.fetch(query, exch_id)

                users = []
                for row in rows:
                    users.append({
                        'user_id': row['user_id'],
                        'exch_id': str(row['exch_id']),
                        'base_currency': row['base_currency'],
                        'timezone': row['timezone'],
                    })

                self.logger.info(f"✅ Retrieved {len(users)} users for exchange: {exch_id}")
                return users

        except Exception as e:
            self.logger.error(f"❌ Error getting users for exchange {exch_id}: {e}")
            return []