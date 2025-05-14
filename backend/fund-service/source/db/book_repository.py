# source/db/book_repository.py
import logging
import time
import decimal
import uuid
import json
from typing import Dict, Any, List, Optional

from source.db.connection_pool import DatabasePool
from source.utils.metrics import track_db_operation

logger = logging.getLogger('book_repository')

def serialize_json_safe(obj):
    """Convert non-JSON serializable objects to serializable types"""
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def ensure_json_serializable(data):
    """Recursively convert all values in a data structure to JSON serializable types"""
    if isinstance(data, dict):
        return {k: ensure_json_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [ensure_json_serializable(item) for item in data]
    elif isinstance(data, (decimal.Decimal, uuid.UUID)):
        return serialize_json_safe(data)
    return data
    
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
            book_id, user_id, name, parameters, created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, to_timestamp($5), to_timestamp($6)
        ) RETURNING book_id
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                # Convert parameters list to JSONB if present
                parameters_json = json.dumps(book_data.get('parameters')) if book_data.get('parameters') else None
                
                book_id = await conn.fetchval(
                    query,
                    book_data['book_id'],
                    book_data['user_id'],
                    book_data['name'],
                    parameters_json, 
                    book_data['created_at'],
                    book_data['updated_at']
                )
                
                duration = time.time() - start_time
                track_db_operation("create_book", True, duration)
                
                # Convert UUID to string before returning
                if isinstance(book_id, uuid.UUID):
                    return str(book_id)
                
                return book_id
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("create_book", False, duration)
            logger.error(f"Error creating book: {e}")
            return None

    async def get_user_books(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all books for a user"""
        pool = await self.db_pool.get_pool()
        
        query = """
        SELECT 
            book_id as id, 
            user_id, 
            name, 
            parameters,
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
                
                # Convert rows to dicts and ensure all values are JSON serializable
                books = [ensure_json_serializable(dict(row)) for row in rows]
                return books
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_user_books", False, duration)
            logger.error(f"Error retrieving books: {e}")
            return []

    async def get_book(self, book_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a single book by ID and user ID"""
        pool = await self.db_pool.get_pool()
        
        query = """
        SELECT 
            book_id as id, 
            user_id, 
            name, 
            parameters,
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
                
                if row:
                    return ensure_json_serializable(dict(row))
                return None
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
        
        # Handle special case for parameters field - convert to JSON
        if 'parameters' in update_data:
            update_data['parameters'] = json.dumps(update_data['parameters'])
        
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