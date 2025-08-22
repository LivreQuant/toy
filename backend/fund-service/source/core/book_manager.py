# source/core/book_manager.py
import logging
import uuid
import json
from typing import Dict, Any, List

from source.models.book import Book

from source.db.book_repository import BookRepository
from source.db.exchange_repository import ExchangeRepository
from source.core.crypto_manager import CryptoManager

from source.utils.metrics import track_book_created

logger = logging.getLogger('book_manager')

class BookManager:
    """Manager for book operations"""

    def __init__(self, 
                 book_repository: BookRepository,
                 crypto_manager: CryptoManager,
                 exchange_repository: ExchangeRepository
                 ):
        """Initialize the book manager with dependencies"""
        self.book_repository = book_repository
        self.crypto_manager = crypto_manager
        self.exchange_repository = exchange_repository

    async def create_book(self, book_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Create a new book for a user with blockchain contract integration and exchange setup
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
            
            # STEP 1: Save to database first
            logger.info(f"Calling repository to save book {book.book_id}")
            db_book_id = await self.book_repository.create_book(book_dict)
            
            if not db_book_id:
                logger.error(f"Repository failed to save book {book.book_id}")
                return {
                    "success": False,
                    "error": "Failed to save book to database"
                }
            
            # STEP 2: Create smart contract
            logger.info(f"Creating smart contract for book {book.book_id}")
            contract_result = await self.crypto_manager.create_contract(user_id, book.book_id, book_dict)
            
            if not contract_result.get("success"):
                logger.error(f"Failed to create contract for book {book.book_id}: {contract_result.get('error')}")
                # Note: We could rollback the book creation here if desired
                return {
                    "success": False,
                    "error": f"Book created but contract creation failed: {contract_result.get('error')}"
                }
            
            logger.info(f"Smart contract created successfully for book {book.book_id}")
            
            # STEP 3: Setup exchange for the book
            logger.info(f"🚀 STARTING EXCHANGE SETUP for book {book.book_id}")
            logger.info(f"🚀 Exchange repository available: {self.exchange_repository is not None}")
            
            initial_capital = book_data.get('initialCapital', 0)
            logger.info(f"🚀 Initial capital value: {initial_capital} (type: {type(initial_capital)})")
            
            if self.exchange_repository is None:
                logger.error(f"❌ Exchange repository is None! Cannot setup exchange for book {book.book_id}")
                return {
                    "success": False,
                    "error": "Exchange repository not initialized"
                }
            
            if initial_capital <= 0:
                logger.warning(f"⚠️ Initial capital is {initial_capital}, setting default value of 10000")
                initial_capital = 10000  # Set a default value
            
            try:
                logger.info(f"🔄 Calling exchange repository setup_exchange_for_book...")
                exchange_result = await self.exchange_repository.setup_exchange_for_book(
                    user_id=user_id,
                    book_id=book.book_id,
                    initial_nav=float(initial_capital)
                )
                
                logger.info(f"🔄 Exchange setup result: {exchange_result}")
                
                if not exchange_result:
                    logger.error(f"❌ Failed to setup exchange for book {book.book_id} - exchange_result is False")
                    # For now, we'll log this as an error but continue
                    # In production, you might want to fail the entire book creation
                else:
                    logger.info(f"✅ Exchange setup completed successfully for book {book.book_id}")
                    
            except Exception as exchange_error:
                logger.error(f"💥 Exception during exchange setup for book {book.book_id}: {exchange_error}")
                logger.exception("Full exchange setup exception:")
                # For now, we'll log this as an error but continue
                # In production, you might want to fail the entire book creation
            
            # Track metrics
            logger.info(f"Book {db_book_id} successfully created, tracking metrics")
            track_book_created(user_id)
            
            return {
                "success": True,
                "book_id": db_book_id,
                "app_id": contract_result.get("app_id")
            }
            
        except Exception as e:
            logger.error(f"Error creating book: {e}")
            logger.exception("Full book creation exception:")
            return {
                "success": False,
                "error": f"Error creating book: {str(e)}"
            }

    async def get_books(self, user_id: str) -> Dict[str, Any]:
        """
        Get all books for a user and convert to new format with contract information
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
                                elif isinstance(value, str):
                                    try:
                                        # Try to parse as JSON first
                                        horizons = json.loads(value)
                                        if isinstance(horizons, list):
                                            conviction_schema['horizons'] = horizons
                                            logger.info(f"Parsed horizons from JSON: {horizons}")
                                        else:
                                            logger.warning(f"Horizons JSON is not a list: {horizons}")
                                            conviction_schema['horizons'] = []
                                    except json.JSONDecodeError:
                                        logger.warning(f"Failed to parse horizons as JSON: {value}")
                                        conviction_schema['horizons'] = []
                                else:
                                    logger.warning(f"Unknown horizons format: {value} (type: {type(value)})")
                                    conviction_schema['horizons'] = []
                
                # Add conviction schema to book
                book['convictionSchema'] = conviction_schema
                
                # Get contract information for this book
                logger.info(f"Getting contract information for book {book_internal['book_id']}")
                try:
                    contract_info = await self.crypto_manager.get_contract(user_id, book_internal['book_id'])
                    logger.info(f"Retrieved contract for user {user_id}, book {book_internal['book_id']}")
                    
                    if contract_info:
                        book['contract'] = contract_info
                        logger.info(f"Added contract info for book {book_internal['book_id']}: app_id={contract_info.get('app_id', 'N/A')}")
                    else:
                        logger.warning(f"No contract found for book {book_internal['book_id']}")
                        book['contract'] = None
                        
                except Exception as contract_error:
                    logger.error(f"Failed to get contract for book {book_internal['book_id']}: {contract_error}")
                    book['contract'] = None
                
                logger.info(f"Final conviction_schema before adding to book: {conviction_schema}")
                
                books.append(book)
            
            return {
                "success": True,
                "books": books
            }
            
        except Exception as e:
            logger.error(f"Error getting books for user {user_id}: {e}")
            logger.exception("Full get_books exception:")
            return {
                "success": False,
                "error": f"Error getting books: {str(e)}"
            }

    async def get_book(self, book_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get a specific book for a user
        """
        logger.info(f"Getting book {book_id} for user {user_id}")
        
        try:
            # Get book from repository
            book_internal = await self.book_repository.get_book(book_id)
            
            if not book_internal:
                return {
                    "success": False,
                    "error": "Book not found"
                }
            
            logger.info(f"Retrieved book {book_id} for user {user_id}")
            
            # Convert to new format (reuse logic from get_books)
            books_result = await self.get_books(user_id)
            if books_result.get("success"):
                for book in books_result["books"]:
                    if book["bookId"] == book_id:
                        return {
                            "success": True,
                            "book": book
                        }
            
            return {
                "success": False,
                "error": "Book not found in converted format"
            }
            
        except Exception as e:
            logger.error(f"Error getting book {book_id} for user {user_id}: {e}")
            return {
                "success": False,
                "error": f"Error getting book: {str(e)}"
            }

    async def update_book(self, book_id: str, book_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Update a book's properties with blockchain contract update
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
            
            # STEP 1: Update smart contract first
            logger.info(f"Updating smart contract for book {book_id}")
            contract_result = await self.crypto_manager.update_contract(user_id, book_id, update_data)
            
            if not contract_result.get("success"):
                logger.error(f"Failed to update contract for book {book_id}: {contract_result.get('error')}")
                return {
                    "success": False,
                    "error": f"Contract update failed: {contract_result.get('error')}"
                }
            
            logger.info(f"Smart contract updated successfully for book {book_id}")
            
            # STEP 2: Update database record
            logger.info(f"Updating database record for book {book_id}")
            success = await self.book_repository.update_book(book_id, user_id, update_data)
            
            if not success:
                logger.error(f"Failed to update book {book_id} in database")
                return {
                    "success": False,
                    "error": "Failed to update book in database"
                }
            
            logger.info(f"Book {book_id} updated successfully")
            
            return {
                "success": True,
                "book_id": book_id,
                "app_id": contract_result.get("app_id")
            }
            
        except Exception as e:
            logger.error(f"Error updating book {book_id}: {e}")
            logger.exception("Full update_book exception:")
            return {
                "success": False,
                "error": f"Error updating book: {str(e)}"
            }


    async def get_book_contract_details(self, book_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get detailed contract information for a book
        
        Args:
            book_id: Book ID
            user_id: User ID
            
        Returns:
            Result dictionary with contract details
        """
        logger.info(f"Getting contract details for book {book_id}, user {user_id}")
        
        try:
            # First verify the book exists and belongs to the user
            book = await self.book_repository.get_book(book_id)
            
            if not book:
                return {
                    "success": False,
                    "error": "Book not found"
                }
            
            if book['user_id'] != user_id:
                return {
                    "success": False,
                    "error": "Book does not belong to this user"
                }
            
            # Get contract information
            contract_data = await self.crypto_manager.get_contract(user_id, book_id)
            
            if not contract_data:
                return {
                    "success": False,
                    "error": "No contract found for this book"
                }
            
            # Get additional contract details if needed
            # You could also fetch transaction history, local state, etc.
            
            return {
                "success": True,
                "contract": {
                    'appId': contract_data.get('app_id'),
                    'appAddress': contract_data.get('app_address'),
                    'status': contract_data.get('status'),
                    'blockchainStatus': contract_data.get('blockchain_status'),
                    'parameters': contract_data.get('parameters'),
                    'activeAt': contract_data.get('active_at'),
                    'contractId': contract_data.get('contract_id'),
                    'bookId': book_id,
                    'userId': user_id
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting contract details for book {book_id}: {e}")
            return {
                "success": False,
                "error": f"Error getting contract details: {str(e)}"
            }

    async def get_client_config(self, user_id: str, book_id: str) -> str:
        """
        Get client config for a user and book
        
        Args:
            user_id: User ID
            book_id: Book ID
            
        Returns:
            Config string (empty string if not found)
        """
        logger.info(f"Getting client config for user {user_id}, book {book_id}")
        
        try:
            config = await self.book_repository.get_client_config(user_id, book_id)
            logger.info(f"Retrieved client config for user {user_id}, book {book_id}: {len(config)} characters")
            return config
        except Exception as e:
            logger.error(f"Error getting client config for user {user_id}, book {book_id}: {e}")
            return ""

    async def update_client_config(self, user_id: str, book_id: str, config: str) -> bool:
        """
        Update client config for a user and book
        
        Args:
            user_id: User ID
            book_id: Book ID
            config: Config string to store
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Updating client config for user {user_id}, book {book_id}")
        
        try:
            success = await self.book_repository.upsert_client_config(user_id, book_id, config)
            if success:
                logger.info(f"Successfully updated client config for user {user_id}, book {book_id}")
            else:
                logger.error(f"Failed to update client config for user {user_id}, book {book_id}")
            return success
        except Exception as e:
            logger.error(f"Error updating client config for user {user_id}, book {book_id}: {e}")
            return False