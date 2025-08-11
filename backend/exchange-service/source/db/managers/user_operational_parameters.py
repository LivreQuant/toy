# source/db/managers/user_operational_parameters.py
from typing import Dict, Optional
from source.db.managers.base_manager import BaseTableManager


class UserOperationalParametersManager(BaseTableManager):
    """Manager for User operational parameters table"""

    async def load_parameters_for_user(self, user_id: str) -> Optional[Dict]:
        """Get PM operational parameters for a specific user"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT 
                        user_id, 
                        max_position_size_pct, 
                        min_position_size_pct, 
                        max_days_to_liquidate
                    FROM exch_us_equity.user_operational_parameters 
                    WHERE user_id = $1
                """
                row = await conn.fetchrow(query, user_id)

                if row:
                    parameters = dict(row)
                    self.logger.info(f"✅ Retrieved PM operational parameters for user: {user_id}")
                    return parameters
                else:
                    self.logger.warning(f"⚠️  No PM operational parameters found for user: {user_id}")
                    return None

        except Exception as e:
            self.logger.error(f"❌ Error getting PM operational parameters for user {user_id}: {e}")
            return None
