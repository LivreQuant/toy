# source/core/book_manager.py
import logging
import time
import uuid
from typing import Dict, Any

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
        logger.info(f"Book data: {book_data}")
        
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
                book_id=book_data.get('book_id', str(uuid.uuid4())),
                status=book_data.get('status', 'active'),
                created_at=book_data.get('created_at', time.time()),
                updated_at=book_data.get('updated_at', time.time())
            )
            
            logger.info(f"Created Book object with ID: {book.book_id}")
            
            # Convert to dictionary for repository layer
            book_dict = book.to_dict()
            
            # Add parameters if they exist
            if 'parameters' in book_data:
                book_dict['parameters'] = book_data['parameters']
            
            # Save to database
            logger.info(f"Calling repository to save book {book.book_id}")
            result = await self.book_repository.create_book(book_dict)
            
            if result:
                # Track metrics
                logger.info(f"Book {book.book_id} successfully created, tracking metrics")
                track_book_created(user_id)
                
                return {
                    "success": True,
                    "book_id": book.book_id
                }
            else:
                logger.error(f"Repository failed to save book {book.book_id}")
                return {
                    "success": False,
                    "error": "Failed to save book"
                }
        except Exception as e:
            logger.error(f"Error creating book: {e}", exc_info=True)
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
            
            # Books are already dictionaries
            logger.info(f"Retrieved {len(books)} books for user {user_id}")
            
            return {
                "success": True,
                "books": books
            }
        except Exception as e:
            logger.error(f"Error getting books for user {user_id}: {e}", exc_info=True)
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
            
            return {
                "success": True,
                "book": book
            }
        except Exception as e:
            logger.error(f"Error getting book {book_id}: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error getting book: {str(e)}"
            }
    
    async def update_book(self, book_id: str, updates: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Update a book's properties
        
        Args:
            book_id: Book ID
            updates: Dictionary of properties to update
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
            
            # Apply updates
            success = await self.book_repository.update_book(book_id, updates)
            
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
            logger.error(f"Error updating book {book_id}: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error updating book: {str(e)}"
            }