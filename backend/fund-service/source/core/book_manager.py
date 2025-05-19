# source/core/book_manager.py
import logging
import uuid
from typing import Dict, Any, List

from source.models.book import Book
from source.db.book_repository import BookRepository
from source.utils.metrics import track_book_created

logger = logging.getLogger('book_manager')

class BookManager:
    """Manager for book operations"""

    def __init__(self, book_repository: BookRepository):
        """Initialize the book manager with dependencies"""
        self.book_repository = book_repository

    async def create_book(self, book_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Create a new book for a user
        
        Args:
            book_data: Book data dictionary
            user_id: User ID
            
        Returns:
            Result dictionary with success flag and book_id
        """
        logger.info(f"Creating book for user {user_id}")
        logger.debug(f"Book data: {book_data}")
        
        # Basic validation for required fields
        if 'name' not in book_data:
            logger.warning(f"Missing required field 'name' in book data")
            return {
                "success": False,
                "error": "Missing required field: name"
            }
        
        # Create book model
        try:
            logger.info(f"Creating Book object with name: {book_data['name']}")
            
            book = Book(
                user_id=user_id,
                name=book_data['name'],
                book_id=book_data.get('book_id', str(uuid.uuid4()))
            )
            
            logger.info(f"Created Book object with ID: {book.book_id}")
            
            # Convert to dictionary for repository layer
            book_dict = book.to_dict()
            
            # Simply pass the parameters directly - they are already in the correct format
            if 'parameters' in book_data:
                book_dict['parameters'] = book_data['parameters']
                logger.info(f"Including {len(book_data['parameters'])} parameters for book")
            
            # Save to database
            logger.info(f"Calling repository to save book {book.book_id}")
            book_id = await self.book_repository.create_book(book_dict)
            
            if book_id:
                # Track metrics
                logger.info(f"Book {book_id} successfully created, tracking metrics")
                track_book_created(user_id)
                
                return {
                    "success": True,
                    "book_id": book_id
                }
            else:
                logger.error(f"Repository failed to save book {book.book_id}")
                return {
                    "success": False,
                    "error": "Failed to save book"
                }
        except Exception as e:
            logger.error(f"Error creating book: {e}")
            return {
                "success": False,
                "error": f"Error creating book: {str(e)}"
            }
    
    async def get_books(self, user_id: str) -> Dict[str, Any]:
        """
        Get all books for a user
        
        Args:
            user_id: User ID
            
        Returns:
            Result dictionary with success flag and books list
        """
        logger.info(f"Getting books for user {user_id}")
        
        try:
            books = await self.book_repository.get_user_books(user_id)
            
            logger.info(f"Retrieved {len(books)} books for user {user_id}")
            
            # Transform the books to ensure consistent format for the client
            transformed_books = []
            for book in books:
                # Create the base book object
                transformed_book = {
                    "book_id": book["book_id"],
                    "user_id": book["user_id"],
                    "name": book["name"],
                    "active_at": book["active_at"]
                }
                
                # Add parameters in the expected triplet format
                if 'parameters' in book:
                    transformed_book["parameters"] = []
                    
                    # Convert key-value parameters to triplet format
                    for field, value in book["parameters"].items():
                        # Map frontend field to category/subcategory
                        # Use the same mapping logic as in repository
                        if field == 'region':
                            category, subcategory = 'Region', ''
                        elif field == 'market':
                            category, subcategory = 'Market', ''
                        elif field == 'instrument':
                            category, subcategory = 'Instrument', ''
                        elif field == 'investmentApproach':
                            category, subcategory = 'Investment Approach', ''
                        elif field == 'investmentTimeframe':
                            category, subcategory = 'Investment Timeframe', ''
                        elif field == 'sector':
                            category, subcategory = 'Sector', ''
                        elif field == 'positionLong':
                            category, subcategory = 'Position', 'Long'
                        elif field == 'positionShort':
                            category, subcategory = 'Position', 'Short'
                        elif field == 'allocation':
                            category, subcategory = 'Allocation', ''
                        elif '.' in field:
                            # Handle direct category.subcategory format
                            parts = field.split('.', 1)
                            category, subcategory = parts[0], parts[1]
                        else:
                            # Default case
                            category, subcategory = field, ''
                        
                        # Add to parameters list
                        transformed_book["parameters"].append([category, subcategory, value])
                
                transformed_books.append(transformed_book)
            
            return {
                "success": True,
                "books": transformed_books
            }
        except Exception as e:
            logger.error(f"Error getting books for user {user_id}: {e}")
            return {
                "success": False,
                "error": f"Error getting books: {str(e)}"
            }
    
    async def get_book(self, book_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get a single book by ID
        
        Args:
            book_id: Book ID
            user_id: User ID to validate ownership
            
        Returns:
            Result dictionary with success flag and book data
        """
        logger.info(f"Getting book {book_id} for user {user_id}")
        
        try:
            book = await self.book_repository.get_book(book_id)
            
            if not book:
                return {
                    "success": False,
                    "error": "Book not found"
                }
            
            # Verify ownership
            if book['user_id'] != user_id:
                return {
                    "success": False,
                    "error": "Book does not belong to this user"
                }
            
            # Transform the book to ensure consistent format for the client
            transformed_book = {
                "book_id": book["book_id"],
                "user_id": book["user_id"],
                "name": book["name"],
                "active_at": book["active_at"]
            }
            
            # Add parameters in the expected triplet format
            if 'parameters' in book:
                transformed_book["parameters"] = []
                
                # Convert key-value parameters to triplet format
                for field, value in book["parameters"].items():
                    # Map frontend field to category/subcategory
                    # Use the same mapping logic as in repository
                    if field == 'region':
                        category, subcategory = 'Region', ''
                    elif field == 'market':
                        category, subcategory = 'Market', ''
                    elif field == 'instrument':
                        category, subcategory = 'Instrument', ''
                    elif field == 'investmentApproach':
                        category, subcategory = 'Investment Approach', ''
                    elif field == 'investmentTimeframe':
                        category, subcategory = 'Investment Timeframe', ''
                    elif field == 'sector':
                        category, subcategory = 'Sector', ''
                    elif field == 'positionLong':
                        category, subcategory = 'Position', 'Long'
                    elif field == 'positionShort':
                        category, subcategory = 'Position', 'Short'
                    elif field == 'allocation':
                        category, subcategory = 'Allocation', ''
                    elif '.' in field:
                        # Handle direct category.subcategory format
                        parts = field.split('.', 1)
                        category, subcategory = parts[0], parts[1]
                    else:
                        # Default case
                        category, subcategory = field, ''
                    
                    # Add to parameters list
                    transformed_book["parameters"].append([category, subcategory, value])
            
            return {
                "success": True,
                "book": transformed_book
            }
        except Exception as e:
            logger.error(f"Error getting book {book_id}: {e}")
            return {
                "success": False,
                "error": f"Error getting book: {str(e)}"
            }
    
    async def update_book(self, book_id: str, update_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
       """
       Update a book's properties using temporal data pattern
       
       Args:
           book_id: Book ID
           update_data: Dictionary of properties to update
           user_id: User ID to validate ownership
           
       Returns:
           Result dictionary with success flag
       """
       logger.info(f"Updating book {book_id} for user {user_id}")
       
       try:
           # First, get the book to verify ownership
           book = await self.book_repository.get_book(book_id)
           
           if not book:
               return {
                   "success": False,
                   "error": "Book not found"
               }
           
           # Verify ownership
           if book['user_id'] != user_id:
               return {
                   "success": False,
                   "error": "Book does not belong to this user"
               }
           
           # Prepare update data
           repository_update = {}
           
           # Handle book name update
           if 'name' in update_data:
               repository_update['name'] = update_data['name']
           
           # Handle parameters update
           if 'parameters' in update_data:
               parameters = {}
               
               # Check if parameters is in triplet format or direct dictionary format
               if isinstance(update_data['parameters'], list):
                   # Convert triplet format to dictionary
                   for param in update_data['parameters']:
                       if len(param) >= 3:
                           category = param[0]
                           subcategory = param[1] if param[1] else ""
                           value = param[2]
                           
                           # Map to frontend field
                           if category == 'Region' and not subcategory:
                               frontend_field = 'region'
                           elif category == 'Market' and not subcategory:
                               frontend_field = 'market'
                           elif category == 'Instrument' and not subcategory:
                               frontend_field = 'instrument'
                           elif category == 'Investment Approach' and not subcategory:
                               frontend_field = 'investmentApproach'
                           elif category == 'Investment Timeframe' and not subcategory:
                               frontend_field = 'investmentTimeframe'
                           elif category == 'Sector' and not subcategory:
                               frontend_field = 'sector'
                           elif category == 'Position' and subcategory == 'Long':
                               frontend_field = 'positionLong'
                           elif category == 'Position' and subcategory == 'Short':
                               frontend_field = 'positionShort'
                           elif category == 'Allocation' and not subcategory:
                               frontend_field = 'allocation'
                           else:
                               # Default fallback - use category/subcategory as the key
                               frontend_field = f"{category}.{subcategory}" if subcategory else category
                               
                           parameters[frontend_field] = value
               elif isinstance(update_data['parameters'], dict):
                   # Already in key-value format
                   parameters = update_data['parameters']
               
               if parameters:
                   repository_update['parameters'] = parameters
           
           # Apply updates using temporal pattern
           success = await self.book_repository.update_book(book_id, repository_update)
           
           if success:
               return {
                   "success": True
               }
           else:
               return {
                   "success": False,
                   "error": "Failed to update book"
               }
       except Exception as e:
           logger.error(f"Error updating book {book_id}: {e}")
           return {
               "success": False,
               "error": f"Error updating book: {str(e)}"
           }