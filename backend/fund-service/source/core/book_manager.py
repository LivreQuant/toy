# source/core/book_manager.py
import logging
import uuid
import json
from typing import Dict, Any, List

from source.models.book import Book

from source.db.book_repository import BookRepository
from source.core.crypto_manager import CryptoManager

from source.utils.metrics import track_book_created

logger = logging.getLogger('book_manager')

class BookManager:
    """Manager for book operations"""

    def __init__(self, 
                 book_repository: BookRepository,
                 crypto_manager: CryptoManager
                 ):
        """Initialize the book manager with dependencies"""
        self.book_repository = book_repository
        self.crypto_manager = crypto_manager

    async def create_book(self, book_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Create a new book for a user with the new data format
        """
        logger.info(f"Creating book for user {user_id}")
        logger.debug(f"Book data: {book_data}")
        
        try:            
            book = Book(
                user_id=user_id,
                book_id=book_data.get('book_id', str(uuid.uuid4()))
            )
            
            logger.info(f"Created Book object with ID: {book.book_id}")
            
            # Convert to dictionary for repository layer
            book_dict = book.to_dict()
            
            # Convert the new format to parameters format
            parameters = []
            
            # Add name parameter
            if 'name' in book_data:
                parameters.append(["Name", "", book_data['name']])
            
            # Add region parameters
            if 'regions' in book_data and isinstance(book_data['regions'], list):
                for region in book_data['regions']:
                    parameters.append(["Region", "", region])
            
            # Add market parameters
            if 'markets' in book_data and isinstance(book_data['markets'], list):
                for market in book_data['markets']:
                    parameters.append(["Market", "", market])
            
            # Add instrument parameters
            if 'instruments' in book_data and isinstance(book_data['instruments'], list):
                for instrument in book_data['instruments']:
                    parameters.append(["Instrument", "", instrument])
            
            # Add investment approach parameters
            if 'investmentApproaches' in book_data and isinstance(book_data['investmentApproaches'], list):
                for approach in book_data['investmentApproaches']:
                    parameters.append(["Investment Approach", "", approach])
            
            # Add investment timeframe parameters
            if 'investmentTimeframes' in book_data and isinstance(book_data['investmentTimeframes'], list):
                for timeframe in book_data['investmentTimeframes']:
                    parameters.append(["Investment Timeframe", "", timeframe])
            
            # Add sector parameters
            if 'sectors' in book_data and isinstance(book_data['sectors'], list):
                for sector in book_data['sectors']:
                    parameters.append(["Sector", "", sector])
            
            # Add position type parameters
            if 'positionTypes' in book_data and isinstance(book_data['positionTypes'], dict):
                position_types = book_data['positionTypes']
                if position_types.get('long'):
                    parameters.append(["Position", "Long", "true"])
                if position_types.get('short'):
                    parameters.append(["Position", "Short", "true"])
            
            # Add initialCapital parameter
            if 'initialCapital' in book_data:
                parameters.append(["Allocation", "", str(book_data['initialCapital'])])
            
            # Add conviction schema parameters
            if 'convictionSchema' in book_data and isinstance(book_data['convictionSchema'], dict):
                conviction_schema = book_data['convictionSchema']
                
                # Portfolio approach
                if 'portfolioApproach' in conviction_schema:
                    parameters.append(["Conviction", "PortfolioApproach", conviction_schema['portfolioApproach']])
                
                # Target conviction method
                if 'targetConvictionMethod' in conviction_schema:
                    parameters.append(["Conviction", "TargetConvictionMethod", conviction_schema['targetConvictionMethod']])
                
                # Incremental conviction method
                if 'incrementalConvictionMethod' in conviction_schema:
                    parameters.append(["Conviction", "IncrementalConvictionMethod", conviction_schema['incrementalConvictionMethod']])
                
                # Max score
                if 'maxScore' in conviction_schema:
                    parameters.append(["Conviction", "MaxScore", str(conviction_schema['maxScore'])])
                
                # Horizons (array)
                if 'horizons' in conviction_schema and isinstance(conviction_schema['horizons'], list):
                    parameters.append(["Conviction", "Horizons", json.dumps(conviction_schema['horizons'])])
            
            # Set parameters in book_dict
            book_dict['parameters'] = parameters
            
            # CREATE SMART CONTRACT
            app_id = await self.crypto_manager.get_contract(book_dict)

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
        Get all books for a user and convert to new format
        """
        logger.info(f"Getting books for user {user_id}")
        
        try:
            # Get books from repository (in internal format)
            books_internal = await self.book_repository.get_user_books(user_id)
            
            logger.info(f"Retrieved {len(books_internal)} books for user {user_id}")
            
            # Convert books to new format
            books = []
            for book_internal in books_internal:
                # Create a book in the new format
                book = {
                    'bookId': book_internal['book_id'],
                    'name': '',
                    'regions': [],
                    'markets': [],
                    'instruments': [],
                    'investmentApproaches': [],
                    'investmentTimeframes': [],
                    'sectors': [],
                    'positionTypes': {'long': False, 'short': False},
                    'initialCapital': 0
                }
                
                # Create empty conviction schema
                conviction_schema = {}
                
                # Extract data from parameters
                parameters = book_internal.get('parameters', [])
                for param in parameters:
                    if len(param) >= 3:
                        category, subcategory, value = param
                        logger.debug(f"Processing param: category='{category}', subcategory='{subcategory}', value='{value}'")
                        
                        if category == 'Name':
                            book['name'] = value
                        elif category == 'Region':
                            book['regions'].append(value)
                        elif category == 'Market':
                            book['markets'].append(value)
                        elif category == 'Instrument':
                            book['instruments'].append(value)
                        elif category == 'Investment Approach':
                            book['investmentApproaches'].append(value)
                        elif category == 'Investment Timeframe':
                            book['investmentTimeframes'].append(value)
                        elif category == 'Sector':
                            book['sectors'].append(value)
                        elif category == 'Position':
                            if subcategory == 'Long':
                                book['positionTypes']['long'] = value.lower() == 'true'
                            elif subcategory == 'Short':
                                book['positionTypes']['short'] = value.lower() == 'true'
                        elif category == 'Allocation':
                            try:
                                book['initialCapital'] = int(value)
                            except (ValueError, TypeError):
                                book['initialCapital'] = 0
                        # Handle conviction schema parameters
                        elif category == 'Conviction':
                            logger.info(f"Found Conviction parameter: subcategory='{subcategory}', value='{value}'")
                            if subcategory == 'PortfolioApproach':
                                conviction_schema['portfolioApproach'] = value
                                logger.debug(f"Set portfolioApproach = '{value}'")
                            elif subcategory == 'TargetConvictionMethod':
                                conviction_schema['targetConvictionMethod'] = value
                                logger.debug(f"Set targetConvictionMethod = '{value}'")
                            elif subcategory == 'IncrementalConvictionMethod':
                                conviction_schema['incrementalConvictionMethod'] = value
                                logger.debug(f"Set incrementalConvictionMethod = '{value}'")
                            elif subcategory == 'MaxScore':
                                try:
                                    conviction_schema['maxScore'] = int(value)
                                    logger.debug(f"Set maxScore = {int(value)}")
                                except (ValueError, TypeError):
                                    conviction_schema['maxScore'] = value
                                    logger.debug(f"Set maxScore = '{value}' (as string)")
                            elif subcategory == 'Horizons':
                                logger.info(f"Processing Horizons: raw value = '{value}', type = {type(value)}")
                                if isinstance(value, list):
                                    # Already a list, use it directly
                                    conviction_schema['horizons'] = value
                                    logger.info(f"Using horizons as-is (already a list): {value}")
                                else:
                                    # It's a string, try to parse as JSON
                                    try:
                                        parsed_horizons = json.loads(value)
                                        conviction_schema['horizons'] = parsed_horizons
                                        logger.info(f"Successfully parsed horizons: {parsed_horizons}")
                                    except (json.JSONDecodeError, TypeError) as e:
                                        logger.error(f"Failed to parse horizons JSON: {e}")
                                        conviction_schema['horizons'] = []
                            else:
                                logger.warning(f"Unknown Conviction subcategory: '{subcategory}'")

                # GET SMART CONTRACT APP_ID
                app_id = await self.crypto_manager.get_contract(book_internal['book_id'])
                
                # Add conviction schema if any values were found
                if conviction_schema:
                    logger.info(f"Final conviction_schema before adding to book: {conviction_schema}")
                    book['convictionSchema'] = conviction_schema
                else:
                    logger.warning("No conviction_schema values found")
                
                books.append(book)
            
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
        Get a single book by ID and convert to new format
        """
        logger.info(f"Getting book {book_id} for user {user_id}")
        
        try:
            # Get book from repository (in internal format)
            book_internal = await self.book_repository.get_book(book_id)
            
            if not book_internal:
                return {
                    "success": False,
                    "error": "Book not found"
                }
            
            # Verify ownership
            if book_internal['user_id'] != user_id:
                return {
                    "success": False,
                    "error": "Book does not belong to this user"
                }
            
            # Create a book in the new format
            book = {
                'bookId': book_internal['book_id'],
                'name': '',
                'regions': [],
                'markets': [],
                'instruments': [],
                'investmentApproaches': [],
                'investmentTimeframes': [],
                'sectors': [],
                'positionTypes': {'long': False, 'short': False},
                'initialCapital': 0
            }
            
            # Create empty conviction schema
            conviction_schema = {}
            
            # Extract data from parameters
            parameters = book_internal.get('parameters', [])
            for param in parameters:
                if len(param) >= 3:
                    category, subcategory, value = param
                    logger.debug(f"Processing param: category='{category}', subcategory='{subcategory}', value='{value}'")
                    
                    if category == 'Name':
                        book['name'] = value
                    elif category == 'Region':
                        book['regions'].append(value)
                    elif category == 'Market':
                        book['markets'].append(value)
                    elif category == 'Instrument':
                        book['instruments'].append(value)
                    elif category == 'Investment Approach':
                        book['investmentApproaches'].append(value)
                    elif category == 'Investment Timeframe':
                        book['investmentTimeframes'].append(value)
                    elif category == 'Sector':
                        book['sectors'].append(value)
                    elif category == 'Position':
                        if subcategory == 'Long':
                            book['positionTypes']['long'] = value.lower() == 'true'
                        elif subcategory == 'Short':
                            book['positionTypes']['short'] = value.lower() == 'true'
                    elif category == 'Allocation':
                        try:
                            book['initialCapital'] = int(value)
                        except (ValueError, TypeError):
                            book['initialCapital'] = 0
                    # Handle conviction schema parameters
                    elif category == 'Conviction':
                        logger.info(f"Found Conviction parameter: subcategory='{subcategory}', value='{value}'")
                        if subcategory == 'PortfolioApproach':
                            conviction_schema['portfolioApproach'] = value
                            logger.debug(f"Set portfolioApproach = '{value}'")
                        elif subcategory == 'TargetConvictionMethod':
                            conviction_schema['targetConvictionMethod'] = value
                            logger.debug(f"Set targetConvictionMethod = '{value}'")
                        elif subcategory == 'IncrementalConvictionMethod':
                            conviction_schema['incrementalConvictionMethod'] = value
                            logger.debug(f"Set incrementalConvictionMethod = '{value}'")
                        elif subcategory == 'MaxScore':
                            try:
                                conviction_schema['maxScore'] = int(value)
                                logger.debug(f"Set maxScore = {int(value)}")
                            except (ValueError, TypeError):
                                conviction_schema['maxScore'] = value
                                logger.debug(f"Set maxScore = '{value}' (as string)")
                        elif subcategory == 'Horizons':
                            logger.info(f"Processing Horizons: raw value = '{value}', type = {type(value)}")
                            if isinstance(value, list):
                                # Already a list, use it directly
                                conviction_schema['horizons'] = value
                                logger.info(f"Using horizons as-is (already a list): {value}")
                            else:
                                # It's a string, try to parse as JSON
                                try:
                                    parsed_horizons = json.loads(value)
                                    conviction_schema['horizons'] = parsed_horizons
                                    logger.info(f"Successfully parsed horizons: {parsed_horizons}")
                                except (json.JSONDecodeError, TypeError) as e:
                                    logger.error(f"Failed to parse horizons JSON: {e}")
                                    conviction_schema['horizons'] = []
                        else:
                            logger.warning(f"Unknown Conviction subcategory: '{subcategory}'")
            
            # GET SMART CONTRACT APP_ID
            app_id = await self.crypto_manager.get_contract(book_id)

            # Add conviction schema if any values were found
            if conviction_schema:
                logger.info(f"Final conviction_schema before adding to book: {conviction_schema}")
                book['convictionSchema'] = conviction_schema
            else:
                logger.warning("No conviction_schema values found")
            
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
        
    async def update_book(self, book_id: str, book_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Update a book's properties using new format
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
            
            # Convert to parameters format for repository
            parameters = []
            
            # Add name parameter
            if 'name' in book_data:
                parameters.append(["Name", "", book_data['name']])
            
            # Add region parameters
            if 'regions' in book_data and isinstance(book_data['regions'], list):
                for region in book_data['regions']:
                    parameters.append(["Region", "", region])
            
            # Add market parameters
            if 'markets' in book_data and isinstance(book_data['markets'], list):
                for market in book_data['markets']:
                    parameters.append(["Market", "", market])
            
            # Add instrument parameters
            if 'instruments' in book_data and isinstance(book_data['instruments'], list):
                for instrument in book_data['instruments']:
                    parameters.append(["Instrument", "", instrument])
            
            # Add investment approach parameters
            if 'investmentApproaches' in book_data and isinstance(book_data['investmentApproaches'], list):
                for approach in book_data['investmentApproaches']:
                    parameters.append(["Investment Approach", "", approach])
            
            # Add investment timeframe parameters
            if 'investmentTimeframes' in book_data and isinstance(book_data['investmentTimeframes'], list):
                for timeframe in book_data['investmentTimeframes']:
                    parameters.append(["Investment Timeframe", "", timeframe])
            
            # Add sector parameters
            if 'sectors' in book_data and isinstance(book_data['sectors'], list):
                for sector in book_data['sectors']:
                    parameters.append(["Sector", "", sector])
            
            # Add position type parameters
            if 'positionTypes' in book_data and isinstance(book_data['positionTypes'], dict):
                position_types = book_data['positionTypes']
                if position_types.get('long'):
                    parameters.append(["Position", "Long", "true"])
                if position_types.get('short'):
                    parameters.append(["Position", "Short", "true"])
            
            # Add initialCapital parameter
            if 'initialCapital' in book_data:
                parameters.append(["Allocation", "", str(book_data['initialCapital'])])
            
            # Add conviction schema parameters
            if 'convictionSchema' in book_data and isinstance(book_data['convictionSchema'], dict):
                conviction_schema = book_data['convictionSchema']
                
                # Portfolio approach
                if 'portfolioApproach' in conviction_schema:
                    parameters.append(["Conviction", "PortfolioApproach", conviction_schema['portfolioApproach']])
                
                # Target conviction method
                if 'targetConvictionMethod' in conviction_schema:
                    parameters.append(["Conviction", "TargetConvictionMethod", conviction_schema['targetConvictionMethod']])
                
                # Incremental conviction method
                if 'incrementalConvictionMethod' in conviction_schema:
                    parameters.append(["Conviction", "IncrementalConvictionMethod", conviction_schema['incrementalConvictionMethod']])
                
                # Max score
                if 'maxScore' in conviction_schema:
                    parameters.append(["Conviction", "MaxScore", str(conviction_schema['maxScore'])])
                
                # Horizons (array)
                if 'horizons' in conviction_schema and isinstance(conviction_schema['horizons'], list):
                    parameters.append(["Conviction", "Horizons", json.dumps(conviction_schema['horizons'])])
            
            # Prepare update data
            update_data = {
                'parameters': parameters
            }
            
            # UPDATE SMART CONTRACT
            result = await self.crypto_manager.update_contract(update_data)

            # Apply updates using temporal pattern
            success = await self.book_repository.update_book(book_id, update_data)
            
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
        