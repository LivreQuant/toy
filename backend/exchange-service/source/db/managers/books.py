# source/db/managers/books.py
from typing import Dict, List
from source.db.managers.base_manager import BaseTableManager


class BooksManager(BaseTableManager):
    """Manager for books table"""

    async def load_books_for_exchange(self, exch_id: str) -> List[Dict]:
        """Get all books for a specific exchange"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT book_id, exch_id, timezone, base_currency, initial_nav, operation_id, engine_id
                    FROM exch_us_equity.books 
                    WHERE exch_id = $1
                """
                rows = await conn.fetch(query, exch_id)

                books = []
                for row in rows:
                    books.append({
                        'book_id': row['book_id'],
                        'exch_id': str(row['exch_id']),
                        'timezone': row['timezone'],
                        'base_currency': row['base_currency'],
                        'initial_nav': row['initial_nav'],
                        'operation_id': row['operation_id'],
                        'engine_id': row['engine_id']
                    })

                self.logger.info(f"✅ Retrieved {len(books)} books for exchange: {exch_id}")
                return books

        except Exception as e:
            self.logger.error(f"❌ Error getting books for exchange {exch_id}: {e}")
            return []