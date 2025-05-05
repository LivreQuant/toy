import logging
import time
from typing import Dict, Any, List, Optional, Tuple
import uuid

from source.db.connection_pool import DatabasePool
from source.models.book import Book
from source.utils.metrics import track_db_operation

logger = logging.getLogger('book_repository')


class BookRepository:
    """Data access layer for books"""

    def __init__(self):
        """Initialize the book repository"""
        self.db_pool = DatabasePool()
    
    async def create_book(self, book: Book) -> bool:
        """Create a new book in the database"""
        pool = await self.db_pool.get_pool()
        
        query = """
        INSERT INTO trading.books (
            book_id, user_id, name, initial_capital, risk_level, market_focus,
            status, trading_strategy, max_position_size, max_total_risk,
            created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, to_timestamp($11), to_timestamp($12)
        )
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    query,
                    book.book_id,
                    book.user_id,
                    book.name,
                    book.initial_capital,
                    book.risk_level,
                    book.market_focus,
                    book.status,
                    book.trading_strategy,
                    book.max_position_size,
                    book.max_total_risk,
                    book.created_at,
                    book.updated_at
                )
                
                duration = time.time() - start_time
                track_db_operation("create_book", True, duration)
                
                return True
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("create_book", False, duration)
            logger.error(f"Error creating book: {e}")
            return False
    
    async def get_books_by_user(self, user_id: str) -> List[Book]:
        """Get all books for a user"""
        pool = await self.db_pool.get_pool()
        
        query = """
        SELECT * FROM trading.books 
        WHERE user_id = $1
        ORDER BY created_at DESC
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(query, user_id)
                
                books = []
                for row in rows:
                    book_data = dict(row)
                    
                    # Convert timestamp to float for created_at and updated_at
                    if 'created_at' in book_data:
                        book_data['created_at'] = book_data['created_at'].timestamp()
                    if 'updated_at' in book_data:
                        book_data['updated_at'] = book_data['updated_at'].timestamp()
                    
                    books.append(Book.from_dict(book_data))
                
                duration = time.time() - start_time
                track_db_operation("get_books_by_user", True, duration)
                
                return books
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_books_by_user", False, duration)
            logger.error(f"Error getting books for user {user_id}: {e}")
            return []
    
    async def get_book(self, book_id: str) -> Optional[Book]:
        """Get a single book by ID"""
        pool = await self.db_pool.get_pool()
        
        query = """
        SELECT * FROM trading.books 
        WHERE book_id = $1
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, book_id)
                
                if not row:
                    return None
                
                book_data = dict(row)
                
                # Convert timestamp to float for created_at and updated_at
                if 'created_at' in book_data:
                    book_data['created_at'] = book_data['created_at'].timestamp()
                if 'updated_at' in book_data:
                    book_data['updated_at'] = book_data['updated_at'].timestamp()
                
                duration = time.time() - start_time
                track_db_operation("get_book", True, duration)
                
                return Book.from_dict(book_data)
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_book", False, duration)
            logger.error(f"Error getting book {book_id}: {e}")
            return None
    
    async def update_book(self, book_id: str, updates: Dict[str, Any]) -> bool:
        """Update a book's properties"""
        if not updates:
            return True  # Nothing to update
        
        pool = await self.db_pool.get_pool()
        
        # Build the SET clause dynamically based on provided updates
        set_fields = []
        params = [book_id]  # First parameter is always the book_id
        
        param_index = 2  # Start from the second parameter
        for key, value in updates.items():
            set_fields.append(f"{key} = ${param_index}")
            params.append(value)
            param_index += 1
        
        # Always update updated_at
        set_fields.append(f"updated_at = to_timestamp(${param_index})")
        params.append(time.time())
        
        query = f"""
        UPDATE trading.books
        SET {', '.join(set_fields)}
        WHERE book_id = $1
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                await conn.execute(query, *params)
                
                duration = time.time() - start_time
                track_db_operation("update_book", True, duration)
                
                return True
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("update_book", False, duration)
            logger.error(f"Error updating book {book_id}: {e}")
            return False
    
    async def delete_book(self, book_id: str) -> bool:
        """Delete a book"""
        pool = await self.db_pool.get_pool()
        
        query = """
        DELETE FROM trading.books 
        WHERE book_id = $1
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                await conn.execute(query, book_id)
                
                duration = time.time() - start_time
                track_db_operation("delete_book", True, duration)
                
                return True
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("delete_book", False, duration)
            logger.error(f"Error deleting book {book_id}: {e}")
            return False
    
    async def check_connection(self) -> bool:
        """Check if database connection is working"""
        try:
            pool = await self.db_pool.get_pool()
            async with pool.acquire() as conn:
                await conn.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False