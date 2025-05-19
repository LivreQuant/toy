# source/db/book_repository.py
import logging
import time
import uuid
import datetime
import json
from typing import Dict, Any, List, Optional

from source.db.connection_pool import DatabasePool
from source.utils.metrics import track_db_operation
from source.utils.property_mappings import get_book_db_mapping, get_original_book_field

logger = logging.getLogger('book_repository')

def ensure_json_serializable(data):
    """Recursively convert all values in a data structure to JSON serializable types"""
    if isinstance(data, dict):
        return {k: ensure_json_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [ensure_json_serializable(item) for item in data]
    elif isinstance(data, datetime.datetime):
        return data.timestamp()
    elif isinstance(data, uuid.UUID):
        return str(data)
    return data

class BookRepository:
    """Data access layer for books using temporal data pattern"""

    def __init__(self):
        """Initialize the book repository"""
        self.db_pool = DatabasePool()
        # Far future date used for active records
        self.future_date = datetime.datetime(2999, 1, 1, tzinfo=datetime.timezone.utc)

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
        
        query = """
        INSERT INTO fund.books (
            book_id, user_id, name, status, active_at, expire_at
        ) VALUES (
            $1, $2, $3, $4, NOW(), $5
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
                        self.future_date
                    )
                    
                    # Process book parameters if present
                    if 'parameters' in book_data:
                        await self._save_book_parameters(conn, book_id, book_data['parameters'])
                    elif 'bookParameters' in book_data:
                        await self._save_book_parameters_dict(conn, book_id, book_data['bookParameters'])
                    
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
            logger.error(f"Error creating book: {e}", exc_info=True)
            return None

    async def _save_book_parameters(self, conn, book_id: str, parameters: List) -> None:
        """
        Save book parameters from legacy list format
        
        Args:
            conn: Database connection
            book_id: Book ID
            parameters: List of parameter triplets [category, subcategory, value]
        """
        logger.info(f"Processing {len(parameters)} parameters for book {book_id}")
        
        now = datetime.datetime.now(datetime.timezone.utc)
        property_query = """
        INSERT INTO fund.book_properties (
            book_id, category, subcategory, value, active_at, expire_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6
        )
        """
        
        try:
            for param in parameters:
                if len(param) >= 3:
                    category = param[0]
                    subcategory = param[1] if param[1] else ""
                    value = param[2]
                                        
                    # Save to database with consistent key
                    await conn.execute(
                        property_query,
                        book_id,
                        category,
                        subcategory,
                        value,
                        now,
                        self.future_date
                    )
        except Exception as e:
            logger.error(f"Error saving book parameters: {e}")
            raise

    async def _save_book_parameters_dict(self, conn, book_id: str, parameters: Dict[str, Any]) -> None:
        """
        Save book parameters from dictionary format using mapping
        
        Args:
            conn: Database connection
            book_id: Book ID
            parameters: Dictionary of parameters {field: value}
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        
        property_query = """
        INSERT INTO fund.book_properties (
            book_id, category, subcategory, value, active_at, expire_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6
        )
        """
        
        try:
            for field, value in parameters.items():
                # Skip if value is None or empty
                if value is None or (isinstance(value, str) and not value.strip()):
                    continue
                
                # Look up the mapping
                db_mapping = get_book_db_mapping(field)
                
                if db_mapping:
                    category, subcategory = db_mapping
                                        
                    # Convert non-string values to JSON strings
                    if not isinstance(value, str):
                        value = json.dumps(value)
                    
                    # Save to database with mapped values
                    await conn.execute(
                        property_query,
                        book_id,
                        category,
                        subcategory,
                        value,
                        now,
                        self.future_date
                    )
                else:
                    # Handle unmapped fields - parse to potential category/subcategory
                    if '.' in field:
                        category, subcategory = field.split('.', 1)
                    else:
                        category = field
                        subcategory = ""
                                        
                    # Convert non-string values to JSON strings
                    if not isinstance(value, str):
                        value = json.dumps(value)
                    
                    # Save with direct mapping
                    await conn.execute(
                        property_query,
                        book_id,
                        category,
                        subcategory,
                        value,
                        now,
                        self.future_date
                    )
        except Exception as e:
            logger.error(f"Error saving book parameters: {e}")
            raise
    
    async def get_user_books(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all books for a user with their properties"""
        pool = await self.db_pool.get_pool()
        
        logger.info(f"Fetching books from database for user {user_id}")
        
        book_query = """
        SELECT DISTINCT ON (book_id)
            book_id, 
            user_id, 
            name,
            status,
            extract(epoch from active_at) as active_at
        FROM fund.books 
        WHERE user_id = $1 AND expire_at > NOW()
        ORDER BY book_id, active_at DESC
        """
        
        property_query = """
        SELECT 
            category,
            subcategory,
            value
        FROM fund.book_properties
        WHERE book_id = $1 AND expire_at > NOW()
        ORDER BY category, subcategory
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
                    
                    # Process properties
                    book_parameters = {}
                    parameters = []  # Legacy format for backward compatibility
                    
                    for prop in property_rows:
                        category = prop['category']
                        subcategory = prop['subcategory']
                        value = prop['value']
                        
                        # Try to parse JSON values
                        try:
                            if value and (value.startswith('{') or value.startswith('[')):
                                value = json.loads(value)
                        except (json.JSONDecodeError, AttributeError):
                            pass
                        
                        # Try to map to original field
                        original_field = get_original_book_field(category, subcategory)
                        
                        if original_field:
                            # Use mapped field name
                            book_parameters[original_field] = value
                        else:
                            # Use category/subcategory as field name
                            if subcategory:
                                field_name = f"{category}.{subcategory}"
                            else:
                                field_name = category
                            book_parameters[field_name] = value
                        
                        # Add to legacy parameters list
                        parameters.append([
                            category,
                            subcategory,
                            value
                        ])
                    
                    # Add both formats to book data
                    book_data['parameters'] = parameters
                    book_data['bookParameters'] = book_parameters
                    
                    # Add book to results
                    books.append(ensure_json_serializable(book_data))
                
                duration = time.time() - start_time
                track_db_operation("get_user_books", True, duration)
                
                logger.info(f"Retrieved {len(books)} books for user {user_id}")
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
        SELECT DISTINCT ON (book_id)
            book_id, 
            user_id, 
            name,
            status,
            extract(epoch from active_at) as active_at
        FROM fund.books 
        WHERE book_id = $1 AND expire_at > NOW()
        ORDER BY book_id, active_at DESC
        """
        
        property_query = """
        SELECT 
            category,
            subcategory,
            value
        FROM fund.book_properties
        WHERE book_id = $1 AND expire_at > NOW()
        ORDER BY category, subcategory
        """
        
        try:
            async with pool.acquire() as conn:
                # Get book
                book_row = await conn.fetchrow(book_query, book_id)
                
                if not book_row:
                    logger.warning(f"Book {book_id} not found or expired")
                    return None
                
                book_data = dict(book_row)
                
                # Get properties
                property_rows = await conn.fetch(property_query, book_id)
                
                # Process properties
                book_parameters = {}
                parameters = []  # Legacy format for backward compatibility
                
                for prop in property_rows:
                    category = prop['category']
                    subcategory = prop['subcategory']
                    value = prop['value']
                    
                    # Try to parse JSON values
                    try:
                        if value and (value.startswith('{') or value.startswith('[')):
                            value = json.loads(value)
                    except (json.JSONDecodeError, AttributeError):
                        pass
                    
                    # Try to map to original field
                    original_field = get_original_book_field(category, subcategory)
                    
                    if original_field:
                        # Use mapped field name
                        book_parameters[original_field] = value
                    else:
                        # Use category/subcategory as field name
                        if subcategory:
                            field_name = f"{category}.{subcategory}"
                        else:
                            field_name = category
                        book_parameters[field_name] = value
                    
                    # Add to legacy parameters list
                    parameters.append([
                        category,
                        subcategory,
                        value
                    ])
                
                # Add both formats to book data
                book_data['parameters'] = parameters
                book_data['bookParameters'] = book_parameters
                
                logger.info(f"Successfully retrieved book {book_id} with {len(parameters)} parameters")
                
                return ensure_json_serializable(book_data)
                
        except Exception as e:
            logger.error(f"Error retrieving book {book_id}: {e}", exc_info=True)
            return None
    
    async def update_book(self, book_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update a book using temporal data pattern (expire and insert new)
        
        Args:
            book_id: Book ID to update
            update_data: Dictionary with fields to update
            
        Returns:
            True if successful, False otherwise
        """
        if not update_data:
            logger.info(f"No updates provided for book {book_id}, skipping")
            return True  # Nothing to update
        
        pool = await self.db_pool.get_pool()
        
        # Extract parameters/bookParameters for separate handling
        parameters = update_data.pop('parameters', None)
        book_parameters = update_data.pop('bookParameters', None)
        
        now = datetime.datetime.now(datetime.timezone.utc)
        
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # Update the book entity if needed
                    if update_data:
                        # Fetch the current active book record
                        current_book = await conn.fetchrow(
                            """
                            SELECT * FROM fund.books
                            WHERE book_id = $1 AND expire_at > NOW()
                            ORDER BY active_at DESC
                            LIMIT 1
                            """,
                            book_id
                        )
                        
                        if not current_book:
                            logger.error(f"No active book found with ID {book_id}")
                            return False
                        
                        # Expire the current record
                        logger.info(f"Expiring current book record for {book_id}")
                        await conn.execute(
                            """
                            UPDATE fund.books
                            SET expire_at = $1
                            WHERE book_id = $2 AND expire_at > NOW()
                            """,
                            now,
                            book_id
                        )
                        
                        # Create a new record with updated values
                        new_record = dict(current_book)
                        
                        # Apply updates, protecting certain fields
                        protected_fields = ['expire_at', 'active_at']
                        for field, value in update_data.items():
                            if field not in protected_fields:
                                new_record[field] = value
                        
                        # Set timestamps
                        new_record['active_at'] = now
                        new_record['expire_at'] = self.future_date
                        
                        # Dynamically build the SQL query
                        columns = list(new_record.keys())
                        placeholders = [f'${i+1}' for i in range(len(columns))]
                        values = [new_record[col] for col in columns]
                        
                        insert_query = f"""
                        INSERT INTO fund.books ({', '.join(columns)})
                        VALUES ({', '.join(placeholders)})
                        """
                        
                        await conn.execute(insert_query, *values)
                    
                    # Update parameters if provided
                    if parameters is not None or book_parameters is not None:
                        # Expire all current parameters
                        await conn.execute(
                            """
                            UPDATE fund.book_properties
                            SET expire_at = $1
                            WHERE book_id = $2 AND expire_at > NOW()
                            """,
                            now,
                            book_id
                        )
                        
                        # Save new parameters
                        if parameters is not None:
                            await self._save_book_parameters(conn, book_id, parameters)
                        elif book_parameters is not None:
                            await self._save_book_parameters_dict(conn, book_id, book_parameters)
                    
                    logger.info(f"Book {book_id} update completed successfully")
                    return True
                    
        except Exception as e:
            logger.error(f"Error updating book {book_id}: {e}", exc_info=True)
            return False