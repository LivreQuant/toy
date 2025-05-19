# source/db/book_repository.py
import logging
import time
import uuid
import datetime
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
        
        # Define which categories should be treated as lists
        self.list_categories = ['Sector', 'Investment Timeframe', 'Investment Approach', 'Instrument']

    async def create_book(self, book_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a new book with its properties using temporal data pattern
        
        Args:
            book_data: Dictionary with book properties including parameters
            
        Returns:
            Book ID if successful, None otherwise
        """
        pool = await self.db_pool.get_pool()
        
        logger.info(f"Creating book in database with ID: {book_data['book_id']}")
        
        now = datetime.datetime.now(datetime.timezone.utc)
        
        book_query = """
        INSERT INTO fund.books (
            book_id, user_id, name, active_at, expire_at
        ) VALUES (
            $1, $2, $3, $4, $5
        ) RETURNING book_id
        """
        
        property_query = """
        INSERT INTO fund.book_properties (
            book_id, category, subcategory, value, active_at, expire_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6
        )
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                # Use a single transaction for the entire operation
                async with conn.transaction():
                    # Insert book
                    logger.info(f"Inserting book record for {book_data['book_id']}")
                    book_id = await conn.fetchval(
                        book_query,
                        book_data['book_id'],
                        book_data['user_id'],
                        book_data['name'],
                        now,
                        self.future_date
                    )
                    
                    # Convert UUID to string
                    if isinstance(book_id, uuid.UUID):
                        book_id = str(book_id)
                    
                    # Process book parameters if present
                    if 'parameters' in book_data and book_data['parameters']:
                        # For triplet format parameters
                        if isinstance(book_data['parameters'], list):
                            logger.info(f"Processing {len(book_data['parameters'])} parameters for book {book_id}")
                            
                            # Group parameters by category and subcategory
                            parameter_groups = {}
                            
                            for param in book_data['parameters']:
                                if len(param) >= 3:
                                    category = param[0]
                                    subcategory = param[1] if param[1] else ""
                                    value = param[2]
                                    
                                    key = (category, subcategory)
                                    
                                    # If this is a field that should be an array
                                    if category in self.list_categories:
                                        if key not in parameter_groups:
                                            parameter_groups[key] = []
                                        
                                        parameter_groups[key].append(value)
                                    else:
                                        # Regular single-value field
                                        parameter_groups[key] = value
                            
                            # Save each parameter or parameter group
                            for (category, subcategory), value in parameter_groups.items():
                                # Format the value - convert arrays to JSON
                                if isinstance(value, list):
                                    value_str = json.dumps(value)
                                else:
                                    # Convert other non-string values to JSON strings
                                    value_str = json.dumps(value) if not isinstance(value, str) else value
                                
                                # Map UI category to DB category and subcategory
                                if category == 'Region':
                                    db_category, db_subcategory = 'property', 'region'
                                elif category == 'Market':
                                    db_category, db_subcategory = 'property', 'market'
                                elif category == 'Instrument':
                                    db_category, db_subcategory = 'property', 'instrument'
                                elif category == 'Investment Approach':
                                    db_category, db_subcategory = 'property', 'approach'
                                elif category == 'Investment Timeframe':
                                    db_category, db_subcategory = 'property', 'timeframe'
                                elif category == 'Sector':
                                    db_category, db_subcategory = 'property', 'sector'
                                elif category == 'Position':
                                    db_category, db_subcategory = 'position', subcategory.lower()
                                elif category == 'Allocation':
                                    db_category, db_subcategory = 'metadata', 'allocation'
                                else:
                                    # Default fallback
                                    db_category, db_subcategory = category.lower(), subcategory.lower()
                                
                                # Insert property
                                await conn.execute(
                                    property_query,
                                    book_id,
                                    db_category,
                                    db_subcategory,
                                    value_str,
                                    now,
                                    self.future_date
                                )
                    
                    duration = time.time() - start_time
                    track_db_operation("create_book", True, duration)
                    
                    logger.info(f"Book created successfully with ID: {book_id}")
                    return book_id
                    
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("create_book", False, duration)
            logger.error(f"Error creating book: {e}", exc_info=True)
            return None

    async def get_user_books(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all books for a user with their properties
        
        Args:
            user_id: User ID
            
        Returns:
            List of book dictionaries with parameters
        """
        pool = await self.db_pool.get_pool()
        
        logger.info(f"Fetching books for user {user_id}")
        
        book_query = """
        SELECT DISTINCT ON (book_id)
            book_id, 
            user_id, 
            name,
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
                # Get all books for this user
                logger.info(f"Executing query to get books for user {user_id}")
                book_rows = await conn.fetch(book_query, user_id)
                
                # Process each book
                books = []
                for book_row in book_rows:
                    book_id = book_row['book_id']
                    if isinstance(book_id, uuid.UUID):
                        book_id = str(book_id)
                    
                    logger.info(f"Processing book {book_id}")
                    
                    # Get book properties
                    property_rows = await conn.fetch(property_query, book_id)
                    logger.info(f"Found {len(property_rows)} properties for book {book_id}")
                    
                    # Process properties into list of triplets for frontend
                    parameters = []
                    
                    for prop in property_rows:
                        category = prop['category']
                        subcategory = prop['subcategory']
                        value = prop['value']
                        
                        # Map DB category/subcategory to UI category/subcategory
                        if category == 'property' and subcategory == 'region':
                            ui_category, ui_subcategory = 'Region', ''
                        elif category == 'property' and subcategory == 'market':
                            ui_category, ui_subcategory = 'Market', ''
                        elif category == 'property' and subcategory == 'instrument':
                            ui_category, ui_subcategory = 'Instrument', ''
                        elif category == 'property' and subcategory == 'approach':
                            ui_category, ui_subcategory = 'Investment Approach', ''
                        elif category == 'property' and subcategory == 'timeframe':
                            ui_category, ui_subcategory = 'Investment Timeframe', ''
                        elif category == 'property' and subcategory == 'sector':
                            ui_category, ui_subcategory = 'Sector', ''
                        elif category == 'position' and subcategory == 'long':
                            ui_category, ui_subcategory = 'Position', 'Long'
                        elif category == 'position' and subcategory == 'short':
                            ui_category, ui_subcategory = 'Position', 'Short'
                        elif category == 'metadata' and subcategory == 'allocation':
                            ui_category, ui_subcategory = 'Allocation', ''
                        else:
                            # Default fallback - use as-is
                            ui_category, ui_subcategory = category, subcategory
                        
                        # Parse JSON arrays for list fields
                        if ui_category in self.list_categories:
                            try:
                                if value and (value.startswith('[') or value.startswith('{')):
                                    parsed_values = json.loads(value)
                                    if isinstance(parsed_values, list):
                                        # Add each value as a separate parameter
                                        for single_value in parsed_values:
                                            parameters.append([ui_category, ui_subcategory, single_value])
                                        continue
                            except (json.JSONDecodeError, AttributeError):
                                pass  # If parsing fails, treat as a single value
                        
                        # Add as a single parameter
                        parameters.append([ui_category, ui_subcategory, value])
                    
                    # Create book dictionary
                    book_data = {
                        'book_id': book_id,
                        'user_id': book_row['user_id'],
                        'name': book_row['name'],
                        'active_at': book_row['active_at'],
                        'parameters': parameters
                    }
                    
                    # Add to results
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
        """
        Get a single book by ID with its properties
        
        Args:
            book_id: Book ID
            
        Returns:
            Book dictionary with parameters if found, None otherwise
        """
        pool = await self.db_pool.get_pool()
        
        logger.info(f"Fetching book {book_id} from database")
        
        book_query = """
        SELECT DISTINCT ON (book_id)
            book_id, 
            user_id, 
            name,
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
                logger.info(f"Executing query to get book {book_id}")
                book_row = await conn.fetchrow(book_query, book_id)
                
                if not book_row:
                    logger.warning(f"Book {book_id} not found or expired")
                    return None
                
                # Process book data
                if isinstance(book_id, uuid.UUID):
                    book_id = str(book_id)
                
                # Get book properties
                property_rows = await conn.fetch(property_query, book_id)
                logger.info(f"Found {len(property_rows)} properties for book {book_id}")
                
                # Process properties into list of triplets for frontend
                parameters = []
                
                for prop in property_rows:
                    category = prop['category']
                    subcategory = prop['subcategory']
                    value = prop['value']
                    
                    # Map DB category/subcategory to UI category/subcategory
                    if category == 'property' and subcategory == 'region':
                        ui_category, ui_subcategory = 'Region', ''
                    elif category == 'property' and subcategory == 'market':
                        ui_category, ui_subcategory = 'Market', ''
                    elif category == 'property' and subcategory == 'instrument':
                        ui_category, ui_subcategory = 'Instrument', ''
                    elif category == 'property' and subcategory == 'approach':
                        ui_category, ui_subcategory = 'Investment Approach', ''
                    elif category == 'property' and subcategory == 'timeframe':
                        ui_category, ui_subcategory = 'Investment Timeframe', ''
                    elif category == 'property' and subcategory == 'sector':
                        ui_category, ui_subcategory = 'Sector', ''
                    elif category == 'position' and subcategory == 'long':
                        ui_category, ui_subcategory = 'Position', 'Long'
                    elif category == 'position' and subcategory == 'short':
                        ui_category, ui_subcategory = 'Position', 'Short'
                    elif category == 'metadata' and subcategory == 'allocation':
                        ui_category, ui_subcategory = 'Allocation', ''
                    else:
                        # Default fallback - use as-is
                        ui_category, ui_subcategory = category, subcategory
                    
                    # Parse JSON arrays for list fields
                    if ui_category in self.list_categories:
                        try:
                            if value and (value.startswith('[') or value.startswith('{')):
                                parsed_values = json.loads(value)
                                if isinstance(parsed_values, list):
                                    # Add each value as a separate parameter
                                    for single_value in parsed_values:
                                        parameters.append([ui_category, ui_subcategory, single_value])
                                    continue
                        except (json.JSONDecodeError, AttributeError):
                            pass  # If parsing fails, treat as a single value
                    
                    # Add as a single parameter
                    parameters.append([ui_category, ui_subcategory, value])
                
                # Create book dictionary
                book_data = {
                    'book_id': book_id,
                    'user_id': book_row['user_id'],
                    'name': book_row['name'],
                    'active_at': book_row['active_at'],
                    'parameters': parameters
                }
                
                logger.info(f"Successfully retrieved book {book_id}")
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
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Extract parameters for separate handling
        parameters = update_data.pop('parameters', None)
        
        logger.info(f"Updating book {book_id} with fields: {list(update_data.keys())} and parameters: {parameters is not None}")
        
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
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
                    
                    # Expire the current book record
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
                    
                    # Apply updates
                    for field, value in update_data.items():
                        if field not in ['expire_at', 'active_at']:  # Protect special fields
                            new_record[field] = value
                    
                    # Set timestamps
                    new_record['active_at'] = now
                    new_record['expire_at'] = self.future_date
                    
                    # Insert the new book record
                    logger.info(f"Creating new book record for {book_id}")
                    columns = list(new_record.keys())
                    placeholders = [f'${i+1}' for i in range(len(columns))]
                    values = [new_record[col] for col in columns]
                    
                    insert_query = f"""
                    INSERT INTO fund.books ({', '.join(columns)})
                    VALUES ({', '.join(placeholders)})
                    """
                    
                    await conn.execute(insert_query, *values)
                    
                    # Update parameters if provided
                    if parameters is not None:
                        # Expire current parameters
                        logger.info(f"Expiring current parameters for book {book_id}")
                        await conn.execute(
                            """
                            UPDATE fund.book_properties
                            SET expire_at = $1
                            WHERE book_id = $2 AND expire_at > NOW()
                            """,
                            now,
                            book_id
                        )
                        
                        # Insert new parameters
                        property_query = """
                        INSERT INTO fund.book_properties (
                            book_id, category, subcategory, value, active_at, expire_at
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6
                        )
                        """
                        
                        # Handle parameter format (triplet list)
                        if isinstance(parameters, list):
                            logger.info(f"Processing {len(parameters)} parameters for book {book_id}")
                            
                            # Group parameters by category and subcategory
                            parameter_groups = {}
                            
                            for param in parameters:
                                if len(param) >= 3:
                                    category = param[0]
                                    subcategory = param[1] if param[1] else ""
                                    value = param[2]
                                    
                                    key = (category, subcategory)
                                    
                                    # If this is a field that should be an array
                                    if category in self.list_categories:
                                        if key not in parameter_groups:
                                            parameter_groups[key] = []
                                        
                                        parameter_groups[key].append(value)
                                    else:
                                        # Regular single-value field
                                        parameter_groups[key] = value
                            
                            # Save each parameter or parameter group
                            for (category, subcategory), value in parameter_groups.items():
                                # Format the value - convert arrays to JSON
                                if isinstance(value, list):
                                    value_str = json.dumps(value)
                                else:
                                    # Convert other non-string values to JSON strings
                                    value_str = json.dumps(value) if not isinstance(value, str) else value
                                
                                # Map UI category to DB category and subcategory
                                if category == 'Region':
                                    db_category, db_subcategory = 'property', 'region'
                                elif category == 'Market':
                                    db_category, db_subcategory = 'property', 'market'
                                elif category == 'Instrument':
                                    db_category, db_subcategory = 'property', 'instrument'
                                elif category == 'Investment Approach':
                                    db_category, db_subcategory = 'property', 'approach'
                                elif category == 'Investment Timeframe':
                                    db_category, db_subcategory = 'property', 'timeframe'
                                elif category == 'Sector':
                                    db_category, db_subcategory = 'property', 'sector'
                                elif category == 'Position':
                                    db_category, db_subcategory = 'position', subcategory.lower()
                                elif category == 'Allocation':
                                    db_category, db_subcategory = 'metadata', 'allocation'
                                else:
                                    # Default fallback
                                    db_category, db_subcategory = category.lower(), subcategory.lower()
                                
                                # Insert property
                                await conn.execute(
                                    property_query,
                                    book_id,
                                    db_category,
                                    db_subcategory,
                                    value_str,
                                    now,
                                    self.future_date
                                )
                    
                    logger.info(f"Book {book_id} update completed successfully")
                    return True
                    
        except Exception as e:
            logger.error(f"Error updating book {book_id}: {e}", exc_info=True)
            return False