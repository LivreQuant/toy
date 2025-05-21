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
        self.list_categories = [
            'Region', 
            'Market', 
            'Sector', 
            'Investment Timeframe', 
            'Investment Approach', 
            'Instrument'
        ]

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
            book_id, user_id, active_at, expire_at        
        ) VALUES (
            $1, $2, $3, $4
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
                        now,
                        self.future_date
                    )
                    
                    # Convert UUID to string
                    if isinstance(book_id, uuid.UUID):
                        book_id = str(book_id)
                    
                    # Process book parameters if present
                    if 'parameters' in book_data and book_data['parameters']:
                        logger.info(f"Processing parameters for book {book_id}")
                        
                        # For triplet format parameters
                        if isinstance(book_data['parameters'], list):
                            logger.info(f"Processing {len(book_data['parameters'])} parameters in list format")
                            
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
                            logger.info(f"Saving {len(parameter_groups)} parameter groups")
                            for (category, subcategory), value in parameter_groups.items():
                                # Format the value - convert arrays to JSON
                                if isinstance(value, list):
                                    value_str = json.dumps(value)
                                else:
                                    # Convert other non-string values to JSON strings
                                    value_str = json.dumps(value) if not isinstance(value, str) else value
                                
                                # Map UI category to DB category and subcategory
                                db_category, db_subcategory = self._map_ui_to_db_category(category, subcategory)
                                
                                logger.debug(f"Inserting property: category={db_category}, subcategory={db_subcategory}, value={value_str[:50]}...")
                                
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
    
    def _map_ui_to_db_category(self, category: str, subcategory: str) -> tuple:
        """Map UI category/subcategory to database category/subcategory"""
        if category == 'Name':
            return 'property', 'name'
        if category == 'Region':
                return 'property', 'region'
        elif category == 'Market':
            return 'property', 'market'
        elif category == 'Instrument':
            return 'property', 'instrument'
        elif category == 'Investment Approach':
            return 'property', 'approach'
        elif category == 'Investment Timeframe':
            return 'property', 'timeframe'
        elif category == 'Sector':
            return 'property', 'sector'
        elif category == 'Position' and subcategory == 'Long':
            return 'position', 'long'
        elif category == 'Position' and subcategory == 'Short':
            return 'position', 'short'
        elif category == 'Allocation':
            return 'metadata', 'allocation'
        # Add conviction model mapping
        elif category == 'Conviction' and subcategory == 'PortfolioApproach':
            return 'conviction_model', 'portfolio_approach'
        elif category == 'Conviction' and subcategory == 'TargetConvictionMethod':
            return 'conviction_model', 'target_conviction_method'
        elif category == 'Conviction' and subcategory == 'IncrementalConvictionMethod':
            return 'conviction_model', 'incremental_conviction_method'
        elif category == 'Conviction' and subcategory == 'MaxScore':
            return 'conviction_model', 'max_score'
        elif category == 'Conviction' and subcategory == 'Horizons':
            return 'conviction_model', 'horizons'
        else:
            # Default fallback - use category/subcategory as-is but lowercase
            return category.lower(), subcategory.lower()
    
    def _map_db_to_ui_category(self, category: str, subcategory: str) -> tuple:
        """Map database category/subcategory to UI category/subcategory"""
        if category == 'property' and subcategory == 'name':
            return 'Name', ''
        if category == 'property' and subcategory == 'region':
            return 'Region', ''
        elif category == 'property' and subcategory == 'market':
            return 'Market', ''
        elif category == 'property' and subcategory == 'instrument':
            return 'Instrument', ''
        elif category == 'property' and subcategory == 'approach':
            return 'Investment Approach', ''
        elif category == 'property' and subcategory == 'timeframe':
            return 'Investment Timeframe', ''
        elif category == 'property' and subcategory == 'sector':
            return 'Sector', ''
        elif category == 'position' and subcategory == 'long':
            return 'Position', 'Long'
        elif category == 'position' and subcategory == 'short':
            return 'Position', 'Short'
        elif category == 'metadata' and subcategory == 'allocation':
            return 'Allocation', ''
        # Add conviction model mapping
        elif category == 'conviction_model' and subcategory == 'portfolio_approach':
            return 'Conviction', 'PortfolioApproach'
        elif category == 'conviction_model' and subcategory == 'target_conviction_method':
            return 'Conviction', 'TargetConvictionMethod'
        elif category == 'conviction_model' and subcategory == 'incremental_conviction_method':
            return 'Conviction', 'IncrementalConvictionMethod'
        elif category == 'conviction_model' and subcategory == 'max_score':
            return 'Conviction', 'MaxScore'
        elif category == 'conviction_model' and subcategory == 'horizons':
            return 'Conviction', 'Horizons'
        else:
            # Default case - first letter uppercase
            return category.capitalize(), subcategory
    
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
                        ui_category, ui_subcategory = self._map_db_to_ui_category(category, subcategory)
                        
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
                        
                        # Try to parse JSON value
                        try:
                            if isinstance(value, str) and (value.startswith('{') or value.startswith('[')):
                                value = json.loads(value)
                        except (json.JSONDecodeError, AttributeError):
                            pass  # If parsing fails, keep as string
                        
                        # Add as a single parameter
                        parameters.append([ui_category, ui_subcategory, value])
                    
                    # Create book dictionary
                    book_data = {
                        'book_id': book_id,
                        'user_id': book_row['user_id'],
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
                if isinstance(book_row['book_id'], uuid.UUID):
                    book_id = str(book_row['book_id'])
                else:
                    book_id = book_row['book_id']
                
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
                    ui_category, ui_subcategory = self._map_db_to_ui_category(category, subcategory)
                    
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
                    
                    # Try to parse JSON value
                    try:
                        if isinstance(value, str) and (value.startswith('{') or value.startswith('[')):
                            value = json.loads(value)
                    except (json.JSONDecodeError, AttributeError):
                        pass  # If parsing fails, keep as string
                    
                    # Add as a single parameter
                    parameters.append([ui_category, ui_subcategory, value])
                
                # Create book dictionary
                book_data = {
                    'book_id': book_id,
                    'user_id': book_row['user_id'],
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
                    
                    # Update the book record directly if we have attributes to update
                    if update_data:
                        logger.info(f"Updating book record for {book_id} with attributes: {update_data}")
                        
                        # Build the SET clause for the update
                        set_clauses = []
                        values = [book_id]  # Start with book_id for the WHERE clause
                        
                        for i, (field, value) in enumerate(update_data.items(), start=2):
                            set_clauses.append(f"{field} = ${i}")
                            values.append(value)
                        
                        if set_clauses:
                            update_query = f"""
                            UPDATE fund.books
                            SET {', '.join(set_clauses)}
                            WHERE book_id = $1 AND expire_at > NOW()
                            """
                            
                            await conn.execute(update_query, *values)
                    
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
                                db_category, db_subcategory = self._map_ui_to_db_category(category, subcategory)
                                
                                logger.debug(f"Inserting updated property: {db_category}, {db_subcategory}, {value_str[:50]}...")
                                
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