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

    def __init__(
            self,
            book_repository: BookRepository,
    ):
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
        
        # Basic validation for required fields
        if 'name' not in book_data:
            return {
                "success": False,
                "error": "Missing required field: name"
            }
        
        # Create book model
        try:
            book = Book(
                user_id=user_id,
                name=book_data['name'],
                parameters=book_data.get('parameters'),
                book_id=str(uuid.uuid4()),
                created_at=time.time(),
                updated_at=time.time()
            )
            
            # Save to database
            success = await self.book_repository.create_book(book)
            
            if success:
                # Track metrics
                track_book_created(user_id)
                
                return {
                    "success": True,
                    "book_id": book.book_id
                }
            else:
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
            books = await self.book_repository.get_books_by_user(user_id)
            
            # Convert Book objects to dictionaries
            book_dicts = [book.to_dict() for book in books]
            
            return {
                "success": True,
                "books": book_dicts
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
            if book.user_id != user_id:
                return {
                    "success": False,
                    "error": "Book does not belong to this user"
                }
            
            return {
                "success": True,
                "book": book.to_dict()
            }
        except Exception as e:
            logger.error(f"Error getting book {book_id}: {e}")
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
            if book.user_id != user_id:
                return {
                    "success": False,
                    "error": "Book does not belong to this user"
                }
            
            # Process updates
            valid_updates = {}
            
            # Only process valid fields
            if 'name' in updates:
                valid_updates['name'] = updates['name']
            
            if 'parameters' in updates:
                valid_updates['parameters'] = updates['parameters']
            
            # Apply updates
            if valid_updates:
                success = await self.book_repository.update_book(book_id, valid_updates)
                
                if success:
                    return {
                        "success": True
                    }
                else:
                    return {
                        "success": False,
                        "error": "Failed to update book"
                    }
            else:
                return {
                    "success": True,
                    "message": "No valid updates provided"
                }
        except Exception as e:
            logger.error(f"Error updating book {book_id}: {e}")
            return {
                "success": False,
                "error": f"Error updating book: {str(e)}"
            }
    
    async def delete_book(self, book_id: str, user_id: str) -> Dict[str, Any]:
        """
        Delete a book
        
        Args:
            book_id: Book ID
            user_id: User ID to validate ownership
            
        Returns:
            Result dictionary with success flag
        """
        logger.info(f"Deleting book {book_id} for user {user_id}")
        
        try:
            # First, get the book to verify ownership
            book = await self.book_repository.get_book(book_id)
            
            if not book:
                return {
                    "success": False,
                    "error": "Book not found"
                }
            
            # Verify ownership
            if book.user_id != user_id:
                return {
                    "success": False,
                    "error": "Book does not belong to this user"
                }
            
            # Delete the book
            success = await self.book_repository.delete_book(book_id)
            
            if success:
                return {
                    "success": True
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to delete book"
                }
        except Exception as e:
            logger.error(f"Error deleting book {book_id}: {e}")
            return {
                "success": False,
                "error": f"Error deleting book: {str(e)}"
            }