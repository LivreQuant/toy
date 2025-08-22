# source/db/managers/book_operational_parameters.py
from typing import Dict, Optional
from source.db.managers.base_manager import BaseTableManager


class BookOperationalParametersManager(BaseTableManager):
    """Manager for Book operational parameters table"""

    async def load_parameters_for_book(self, book_id: str) -> Optional[Dict]:
        """Get PM operational parameters for a specific book"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT 
                        book_id, 
                        max_position_size_pct, 
                        min_position_size_pct, 
                        max_days_to_liquidate
                    FROM exch_us_equity.book_operational_parameters 
                    WHERE book_id = $1
                """
                row = await conn.fetchrow(query, book_id)

                if row:
                    parameters = dict(row)
                    self.logger.info(f"✅ Retrieved PM operational parameters for book: {book_id}")
                    return parameters
                else:
                    self.logger.warning(f"⚠️  No PM operational parameters found for book: {book_id}")
                    return None

        except Exception as e:
            self.logger.error(f"❌ Error getting PM operational parameters for book {book_id}: {e}")
            return None
