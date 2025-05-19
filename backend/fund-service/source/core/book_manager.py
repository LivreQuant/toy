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
            
            # Ensure parameters are properly handled
            if 'parameters' in book_data:
                # Validate parameters format
                if isinstance(book_data['parameters'], list):
                    book_dict['parameters'] = book_data['parameters']
                    param_count = len(book_data['parameters'])
                    logger.info(f"Including {param_count} parameters for book")
                else:
                    # Convert dict parameters to list format if needed
                    params_list = []
                    for key, value in book_data['parameters'].items():
                        category, subcategory = self._split_parameter_key(key)
                        params_list.append([category, subcategory, value])
                    book_dict['parameters'] = params_list
                    logger.info(f"Converted dict parameters to list format, count: {len(params_list)}")
            else:
                # Ensure we always have an empty parameters list
                book_dict['parameters'] = []
                logger.info("No parameters provided, using empty list")
            
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
    
    def _split_parameter_key(self, key: str) -> tuple:
        """Split parameter key into category and subcategory"""
        if '.' in key:
            parts = key.split('.', 1)
            return parts[0], parts[1]
        
        # Handle special cases
        if key == 'region':
            return 'Region', ''
        elif key == 'market':
            return 'Market', ''
        elif key == 'instrument':
            return 'Instrument', ''
        elif key == 'investmentApproach':
            return 'Investment Approach', ''
        elif key == 'investmentTimeframe':
            return 'Investment Timeframe', ''
        elif key == 'sector':
            return 'Sector', ''
        elif key == 'positionLong':
            return 'Position', 'Long'
        elif key == 'positionShort':
            return 'Position', 'Short'
        elif key == 'allocation':
            return 'Allocation', ''
        
        # Default case
        return key, ''
    
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
            
            # Books should already be properly transformed in the repository
            return {
                "success": True,
                "books": books
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
            
            # Book should already be properly transformed in the repository
            return {
                "success": True,
                "book": book
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
               # Ensure parameters are in correct format for repository
               if isinstance(update_data['parameters'], list):
                   repository_update['parameters'] = update_data['parameters']
                   logger.info(f"Updating book with {len(update_data['parameters'])} parameters")
               else:
                   # Convert dict parameters to list format if needed
                   params_list = []
                   for key, value in update_data['parameters'].items():
                       category, subcategory = self._split_parameter_key(key)
                       params_list.append([category, subcategory, value])
                   repository_update['parameters'] = params_list
                   logger.info(f"Converted dict parameters to list format, count: {len(params_list)}")
           
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