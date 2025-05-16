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

def ensure_json_serializable(data):
    """Recursively convert all values in a data structure to JSON serializable types"""
    if isinstance(data, dict):
        return {k: ensure_json_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [ensure_json_serializable(item) for item in data]
    elif isinstance(data, decimal.Decimal):
        return float(data)
    elif isinstance(data, uuid.UUID):
        return str(data)
    return data

class BookRepository:
    """Data access layer for books"""

    def __init__(self):
        """Initialize the book repository"""
        self.db_pool = DatabasePool()

    async def create_book(self, book_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a new book with its properties
        
        Args:
            book_data: Dictionary with book properties including parameters
            
        Returns:
            Book ID if successful, None otherwise
        """
        pool = await self.db_pool.get_pool()
        
        logger.info(f"Creating book in database with ID: {book_data['book_id']}")
        logger.debug(f"Book data keys: {list(book_data.keys())}")
        
        query = """
        INSERT INTO fund.books (
            book_id, user_id, name, status, created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, to_timestamp($5), to_timestamp($6)
        ) RETURNING book_id
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                # Use a single transaction for the entire operation
                async with conn.transaction():
                    # Insert book
                    book_id = await conn.fetchval(
                        query,
                        book_data['book_id'],
                        book_data['user_id'],
                        book_data['name'],
                        book_data.get('status', 'active'),
                        book_data['created_at'],
                        book_data['updated_at']
                    )
                    
                    # Convert parameters list to properties if present
                    parameters = book_data.get('parameters')
                    if parameters and isinstance(parameters, list):
                        logger.info(f"Processing {len(parameters)} parameters for book {book_id}")
                        
                        # Save each parameter individually
                        property_query = """
                        INSERT INTO fund.book_properties (
                            book_id, category, subcategory, key, value
                        ) VALUES (
                            $1, $2, $3, $4, $5
                        )
                        """
                        
                        # Keep track of categories to generate unique keys
                        category_counts = {}
                        
                        # Process all parameters
                        for param in parameters:
                            if len(param) >= 3:
                                category = param[0]
                                subcategory = param[1] if param[1] else ""
                                value = param[2]
                                
                                # Generate unique key by adding counter for duplicate categories
                                if category in category_counts:
                                    category_counts[category] += 1
                                    key = f"{category}_{category_counts[category]}"
                                else:
                                    category_counts[category] = 0
                                    key = category
                                
                                # Execute insert
                                await conn.execute(
                                    property_query,
                                    book_id,
                                    category,
                                    subcategory,
                                    key,
                                    str(value)
                                )
                
                duration = time.time() - start_time
                track_db_operation("create_book", True, duration)
                
                # Convert UUID to string before returning
                if isinstance(book_id, uuid.UUID):
                    book_id_str = str(book_id)
                    logger.info(f"Book created successfully with ID: {book_id_str}")
                    return book_id_str
                
                logger.info(f"Book created successfully with ID: {book_id}")
                return book_id
                
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("create_book", False, duration)
            logger.error(f"Error creating book in database: {e}", exc_info=True)
            return None
    
    async def get_user_books(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all books for a user with their properties"""
        pool = await self.db_pool.get_pool()
        
        logger.info(f"Fetching books from database for user {user_id}")
        
        book_query = """
        SELECT 
            book_id, 
            user_id, 
            name,
            status,
            extract(epoch from created_at) as created_at,
            extract(epoch from updated_at) as updated_at
        FROM fund.books 
        WHERE user_id = $1
        ORDER BY created_at DESC
        """
        
        property_query = """
        SELECT 
            category,
            subcategory,
            value
        FROM fund.book_properties
        WHERE book_id = $1
        ORDER BY category, subcategory, key
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                # Get books
                book_rows = await conn.fetch(book_query, user_id)
                books = []
                
                logger.info(f"Found {len(book_rows)} books for user {user_id}")
                
                # For each book, get its properties
                for book_row in book_rows:
                    book_data = dict(book_row)
                    book_id = book_data['book_id']
                    
                    # Get properties
                    property_rows = await conn.fetch(property_query, book_id)
                    
                    # Reconstruct parameters format
                    parameters = []
                    for prop in property_rows:
                        # Convert back to the original triplet format
                        parameters.append([
                            prop['category'],
                            prop['subcategory'],
                            prop['value']
                        ])
                    
                    # Add parameters to book data
                    book_data['parameters'] = parameters
                    
                    # Add book to results
                    books.append(ensure_json_serializable(book_data))
                
                duration = time.time() - start_time
                track_db_operation("get_user_books", True, duration)
                
                return books
                
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_user_books", False, duration)
            logger.error(f"Error retrieving books: {e}", exc_info=True)
            return []
    
    async def get_book(self, book_id: str) -> Optional[Dict[str, Any]]:
        """Get a single book by ID with its properties"""
        pool = await self.db_pool.get_pool()
        
        logger.info(f"Fetching book {book_id} from database")
        
        book_query = """
        SELECT 
            book_id, 
            user_id, 
            name,
            status,
            extract(epoch from created_at) as created_at,
            extract(epoch from updated_at) as updated_at
        FROM fund.books 
        WHERE book_id = $1
        """
        
        property_query = """
        SELECT 
            category,
            subcategory,
            value
        FROM fund.book_properties
        WHERE book_id = $1
        ORDER BY category, subcategory, key
        """
        
        try:
            async with pool.acquire() as conn:
                # Get book
                book_row = await conn.fetchrow(book_query, book_id)
                
                if not book_row:
                    logger.warning(f"Book {book_id} not found")
                    return None
                
                book_data = dict(book_row)
                
                # Get properties
                property_rows = await conn.fetch(property_query, book_id)
                
                # Reconstruct parameters format
                parameters = []
                for prop in property_rows:
                    # Convert back to the original triplet format
                    parameters.append([
                        prop['category'],
                        prop['subcategory'],
                        prop['value']
                    ])
                
                # Add parameters to book data
                book_data['parameters'] = parameters
                
                logger.info(f"Successfully retrieved book {book_id} with {len(parameters)} parameters")
                
                return ensure_json_serializable(book_data)
                
        except Exception as e:
            logger.error(f"Error retrieving book {book_id}: {e}", exc_info=True)
            return None
    
    async def update_book(self, book_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update a book and its properties
        
        Args:
            book_id: Book ID to update
            update_data: Dictionary with fields to update
            
        Returns:
            True if successful, False otherwise
        """
        if not update_data:
            return True  # Nothing to update
        
        pool = await self.db_pool.get_pool()
        logger.info(f"Updating book {book_id} with fields: {list(update_data.keys())}")
        
        # Handle parameters separately
        parameters = update_data.pop('parameters', None)
        
        # Build dynamic query for book updates
        update_parts = []
        update_values = [book_id]  # First parameter is book_id
        
        param_index = 2  # Start after book_id parameter
        
        for key, value in update_data.items():
            update_parts.append(f"{key} = ${param_index}")
            update_values.append(value)
            param_index += 1
        
        # Always update the updated_at timestamp
        update_parts.append("updated_at = NOW()")
        
        if not update_parts:
            # Only updating parameters, no book fields to update
            book_query = None
        else:
            book_query = f"""
            UPDATE fund.books 
            SET {', '.join(update_parts)}
            WHERE book_id = $1
            """
        
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # Update book if needed
                    if book_query:
                        await conn.execute(book_query, *update_values)
                        logger.info(f"Updated book {book_id} fields")
                    
                    # Update parameters if provided
                    if parameters is not None:
                        # First delete existing properties
                        await conn.execute(
                            "DELETE FROM fund.book_properties WHERE book_id = $1",
                            book_id
                        )
                        logger.info(f"Deleted existing properties for book {book_id}")
                        
                        # Keep track of categories to generate unique keys
                        category_counts = {}
                        
                        # Save each parameter individually
                        property_query = """
                        INSERT INTO fund.book_properties (
                            book_id, category, subcategory, key, value
                        ) VALUES (
                            $1, $2, $3, $4, $5
                        )
                        """
                        
                        # Process all parameters
                        for param in parameters:
                            if len(param) >= 3:
                                category = param[0]
                                subcategory = param[1] if param[1] else ""
                                value = param[2]
                                
                                # Generate unique key by adding counter for duplicate categories
                                if category in category_counts:
                                    category_counts[category] += 1
                                    key = f"{category}_{category_counts[category]}"
                                else:
                                    category_counts[category] = 0
                                    key = category
                                
                                # Execute insert
                                await conn.execute(
                                    property_query,
                                    book_id,
                                    category,
                                    subcategory,
                                    key,
                                    str(value)
                                )
                        
                        logger.info(f"Saved {len(parameters)} new parameters for book {book_id}")
                    
                    return True
                    
        except Exception as e:
            logger.error(f"Error updating book {book_id}: {e}", exc_info=True)
            return False