import logging
import time
from typing import Dict, Any, List, Optional

from source.db.connection_pool import DatabasePool
from source.utils.metrics import track_db_operation

logger = logging.getLogger('book_repository')

class BookRepository:
    """Data access layer for books"""

    def __init__(self):
        """Initialize the book repository"""
        self.db_pool = DatabasePool()

    async def create_book(self, book_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a new book for a user
        
        Args:
            book_data: Dictionary with book properties
            
        Returns:
            Book ID if successful, None otherwise
        """
        pool = await self.db_pool.get_pool()
        
        query = """
        INSERT INTO trading.books (
            book_id, user_id, name, initial_capital, risk_level,
            market_focus, trading_strategy, max_position_size, 
            max_total_risk, status, created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, to_timestamp($11), to_timestamp($12)
        ) RETURNING book_id
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                book_id = await conn.fetchval(
                    query,
                    book_data['book_id'],
                    book_data['user_id'],
                    book_data['name'],
                    book_data['initial_capital'],
                    book_data['risk_level'],
                    book_data.get('market_focus'),
                    book_data.get('trading_strategy'),
                    book_data.get('max_position_size'),
                    book_data.get('max_total_risk'),
                    book_data['status'],
                    book_data['created_at'],
                    book_data['updated_at']
                )
                
                duration = time.time() - start_time
                track_db_operation("create_book", True, duration)
                
                return book_id
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("create_book", False, duration)
            logger.error(f"Error creating book: {e}")
            return None

    async def get_user_books(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all books for a user
        
        Args:
            user_id: User ID to find books for
            
        Returns:
            List of book objects
        """
        pool = await self.db_pool.get_pool()
        
        query = """
        SELECT 
            book_id as id, 
            user_id, 
            name, 
            initial_capital as "initialCapital", 
            risk_level as "riskLevel", 
            market_focus as "marketFocus", 
            trading_strategy as "tradingStrategy",
            max_position_size as "maxPositionSize",
            max_total_risk as "maxTotalRisk",
            status,
            extract(epoch from created_at) as "createdAt",
            extract(epoch from updated_at) as "updatedAt"
        FROM trading.books 
        WHERE user_id = $1
        ORDER BY created_at DESC
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(query, user_id)
                
                duration = time.time() - start_time
                track_db_operation("get_user_books", True, duration)
                
                return [dict(row) for row in rows]
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_user_books", False, duration)
            logger.error(f"Error retrieving books: {e}")
            return []

    async def get_book(self, book_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a single book by ID and user ID
        
        Args:
            book_id: Book ID to retrieve
            user_id: User ID to validate ownership
            
        Returns:
            Book object if found, None otherwise
        """
        pool = await self.db_pool.get_pool()
        
        query = """
        SELECT 
            book_id as id, 
            user_id, 
            name, 
            initial_capital as "initialCapital", 
            risk_level as "riskLevel", 
            market_focus as "marketFocus", 
            trading_strategy as "tradingStrategy",
            max_position_size as "maxPositionSize",
            max_total_risk as "maxTotalRisk",
            status,
            extract(epoch from created_at) as "createdAt",
            extract(epoch from updated_at) as "updatedAt"
        FROM trading.books 
        WHERE book_id = $1 AND user_id = $2
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, book_id, user_id)
                
                duration = time.time() - start_time
                track_db_operation("get_book", True, duration)
                
                return dict(row) if row else None
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_book", False, duration)
            logger.error(f"Error retrieving book: {e}")
            return None

    async def update_book(self, book_id: str, user_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update a book
        
        Args:
            book_id: Book ID to update
            user_id: User ID to validate ownership
            update_data: Dictionary with fields to update
            
        Returns:
            True if successful, False otherwise
        """
        if not update_data:
            return True  # Nothing to update
        
        pool = await self.db_pool.get_pool()
        
        # Build dynamic query based on provided fields
        set_clauses = [f"{key} = ${i+3}" for i, key in enumerate(update_data.keys())]
        set_clause = ", ".join(set_clauses)
        
        query = f"""
        UPDATE trading.books 
        SET {set_clause}
        WHERE book_id = $1 AND user_id = $2
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                params = [book_id, user_id] + list(update_data.values())
                result = await conn.execute(query, *params)
                
                duration = time.time() - start_time
                success = result == "UPDATE 1"
                track_db_operation("update_book", success, duration)
                
                return success
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("update_book", False, duration)
            logger.error(f"Error updating book: {e}")
            return False