import logging
import time
import uuid
from typing import Dict, Any, List, Optional

from source.models.book import Book
from source.db.book_repository import BookRepository
from source.core.validation_manager import ValidationManager
from source.utils.metrics import track_book_created

logger = logging.getLogger('book_manager')


class BookManager:
    """Manager for book operations"""

    def __init__(
            self,
            book_repository: BookRepository,
            validation_manager: ValidationManager
    ):
        """Initialize the book manager with dependencies"""
        self.book_repository = book_repository
        self.validation_manager = validation_manager
    
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
        
        # Validate book parameters
        validation_result = await self.validate_book_parameters(book_data)
        if not validation_result['valid']:
            return {
                "success": False,
                "error": validation_result['error']
            }
        
        # Create book model
        try:
            book = Book(
                user_id=user_id,
                name=book_data['name'],
                initial_capital=float(book_data['initial_capital']),
                risk_level=book_data['risk_level'],
                market_focus=book_data.get('market_focus'),
                trading_strategy=book_data.get('trading_strategy'),
                max_position_size=float(book_data['max_position_size']) if book_data.get('max_position_size') else None,
                max_total_risk=float(book_data['max_total_risk']) if book_data.get('max_total_risk') else None,
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
            
            # Validate update parameters
            valid_updates = {}
            
            # Filter and process updates
            if 'name' in updates:
                valid_updates['name'] = updates['name']
            
            if 'initial_capital' in updates:
                try:
                    valid_updates['initial_capital'] = float(updates['initial_capital'])
                except ValueError:
                    return {
                        "success": False,
                        "error": "Initial capital must be a number"
                    }
            
            if 'risk_level' in updates:
                risk_level = updates['risk_level']
                if risk_level not in ['low', 'medium', 'high']:
                    return {
                        "success": False,
                        "error": "Risk level must be 'low', 'medium', or 'high'"
                    }
                valid_updates['risk_level'] = risk_level
            
            if 'market_focus' in updates:
                valid_updates['market_focus'] = updates['market_focus']
            
            if 'status' in updates:
                status = updates['status']
                if status not in ['CONFIGURED', 'ACTIVE', 'ARCHIVED']:
                    return {
                        "success": False,
                        "error": "Status must be 'CONFIGURED', 'ACTIVE', or 'ARCHIVED'"
                    }
                valid_updates['status'] = status
            
            if 'trading_strategy' in updates:
                valid_updates['trading_strategy'] = updates['trading_strategy']
            
            if 'max_position_size' in updates:
                try:
                    valid_updates['max_position_size'] = float(updates['max_position_size']) if updates['max_position_size'] is not None else None
                except ValueError:
                    return {
                        "success": False,
                        "error": "Max position size must be a number"
                    }
            
            if 'max_total_risk' in updates:
                try:
                    valid_updates['max_total_risk'] = float(updates['max_total_risk']) if updates['max_total_risk'] is not None else None
                except ValueError:
                    return {
                        "success": False,
                        "error": "Max total risk must be a number"
                    }
            
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
    
    async def validate_book_parameters(self, book_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate book parameters
        
        Args:
            book_data: Book data dictionary
            
        Returns:
            Validation result with valid flag and error message
        """
        # Check required fields
        required_fields = ['name', 'initial_capital', 'risk_level']
        for field in required_fields:
            if field not in book_data:
                return {
                    "valid": False,
                    "error": f"Missing required field: {field}"
                }
        
        # Validate risk level
        if book_data['risk_level'] not in ['low', 'medium', 'high']:
            return {
                "valid": False,
                "error": "Risk level must be 'low', 'medium', or 'high'"
            }
        
        # Validate initial capital
        try:
            initial_capital = float(book_data['initial_capital'])
            if initial_capital <= 0:
                return {
                    "valid": False,
                    "error": "Initial capital must be greater than 0"
                }
        except ValueError:
            return {
                "valid": False,
                "error": "Initial capital must be a number"
            }
        
        # Validate max position size if provided
        if 'max_position_size' in book_data and book_data['max_position_size'] is not None:
            try:
                max_position_size = float(book_data['max_position_size'])
                if max_position_size <= 0:
                    return {
                        "valid": False,
                        "error": "Max position size must be greater than 0"
                    }
            except ValueError:
                return {
                    "valid": False,
                    "error": "Max position size must be a number"
                }
        
        # Validate max total risk if provided
        if 'max_total_risk' in book_data and book_data['max_total_risk'] is not None:
            try:
                max_total_risk = float(book_data['max_total_risk'])
                if max_total_risk <= 0:
                    return {
                        "valid": False,
                        "error": "Max total risk must be greater than 0"
                    }
            except ValueError:
                return {
                    "valid": False,
                    "error": "Max total risk must be a number"
                }
        
        return {
            "valid": True
        }