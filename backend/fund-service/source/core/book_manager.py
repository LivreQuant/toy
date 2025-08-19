# source/core/book_manager.py
import logging
import uuid
import json
import aiohttp
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, time

from source.models.book import Book
from source.db.user_repository import UserRepository
from source.db.book_repository import BookRepository
from source.core.crypto_manager import CryptoManager
from source.utils.metrics import track_book_created
from source.config import config

logger = logging.getLogger('book_manager')

class BookManager:
    """Manager for book operations"""

    def __init__(self, 
                 book_repository: BookRepository,
                 crypto_manager: CryptoManager,
                 user_repository: UserRepository = None
                 ):
        """Initialize the book manager with dependencies"""
        self.book_repository = book_repository
        self.crypto_manager = crypto_manager
        self.user_repository = user_repository
        self._http_session = None

    async def _get_http_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session for orchestrator communication"""
        if self._http_session is None or self._http_session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self._http_session = aiohttp.ClientSession(timeout=timeout)
        return self._http_session

    async def close(self):
        """Close HTTP session"""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
            self._http_session = None

    async def _create_exchange_metadata(self, book_id: str) -> str:
        """Create exchange metadata in exch_us_equity.metadata table"""
        try:
            # Generate unique exchange ID
            exch_id = str(uuid.uuid4())
            
            # Get database connection from repository
            async with self.book_repository.get_connection() as conn:
                # Insert exchange metadata - generic exchange service for this book
                await conn.execute("""
                    INSERT INTO exch_us_equity.metadata (
                        exch_id,
                        exchange_type,
                        exchanges,
                        timezone,
                        pre_market_open,
                        market_open,
                        market_close,
                        post_market_close,
                        endpoint,
                        pod_name,
                        namespace,
                        last_snap,
                        updated_time
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13
                    )
                """, 
                exch_id,
                'US_EQUITIES',
                [f'BOOK_{book_id[:8]}'],
                'America/New_York',
                time(4, 0),
                time(9, 30),
                time(16, 0),
                time(20, 0),
                f'http://exchange-{exch_id[:8]}:50055',
                f'exchange-{exch_id[:8]}',
                'default',
                None,
                datetime.utcnow()
                )
                
                logger.info(f"Created exchange metadata with exch_id: {exch_id} for book: {book_id}")
                return exch_id
                
        except Exception as e:
            logger.error(f"Failed to create exchange metadata: {e}")
            return None

    async def _start_exchange_via_orchestrator(self, exch_id: str) -> bool:
        """Start exchange service via orchestrator REST API"""
        try:
            session = await self._get_http_session()
            
            # Call orchestrator start endpoint
            async with session.post(
                f"{config.orchestrator_service_url}/exchanges/{exch_id}/start",
                headers={'Content-Type': 'application/json'}
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Successfully started exchange service: {data}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to start exchange service: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error communicating with orchestrator: {e}")
            return False

    async def create_book(self, book_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Create a new book for a user with blockchain contract integration and exchange service
        """
        logger.info(f"Creating book for user {user_id}")
        logger.debug(f"Book data: {book_data}")
        
        try:            
            book = Book(
                user_id=user_id,
                book_id=book_data.get('book_id', str(uuid.uuid4()))
            )
            
            logger.info(f"Created Book object with ID: {book.book_id}")
            
            # Extract initial capital from book data
            initial_capital = book_data.get('initialCapital', 1000000.0)
            
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
            position_types = book_data.get('positionTypes', {})
            if position_types.get('long', False):
                parameters.append(["Position Type", "", "Long"])
            if position_types.get('short', False):
                parameters.append(["Position Type", "", "Short"])
            
            # Add initial capital parameter
            if 'initialCapital' in book_data:
                parameters.append(["Initial Capital", "", str(book_data['initialCapital'])])
            
            # Add conviction schema if provided
            if 'convictionSchema' in book_data:
                conviction_schema = book_data['convictionSchema']
                
                # Levels (array)
                if 'levels' in conviction_schema and isinstance(conviction_schema['levels'], list):
                    parameters.append(["Conviction", "Levels", json.dumps(conviction_schema['levels'])])
                
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
            
            # STEP 3: Create exchange metadata and start exchange service
            exch_id = await self._create_exchange_metadata(book.book_id)
            if not exch_id:
                logger.warning(f"Failed to create exchange metadata for book {book.book_id}")
                # Don't fail book creation, but log the issue
            else:
                # STEP 4: Setup user portfolio in exchange
                logger.info(f"Setting up user portfolio for {user_id} on exchange {exch_id}")
                portfolio_setup = await self._setup_user_portfolio(user_id, exch_id, initial_capital)
                if not portfolio_setup:
                    logger.warning(f"Failed to setup user portfolio for {user_id} on exchange {exch_id}")
                
                # STEP 5: Start exchange service via orchestrator
                exchange_started = await self._start_exchange_via_orchestrator(exch_id)
                if exchange_started:
                    logger.info(f"Successfully started exchange service for book {book.book_id}")
                else:
                    logger.warning(f"Failed to start exchange service for book {book.book_id}")
            
            # Track metrics
            logger.info(f"Book {db_book_id} successfully created, tracking metrics")
            track_book_created(user_id)
            
            return {
                "success": True,
                "book_id": db_book_id,
                "app_id": contract_result.get("app_id"),
                "exchange_id": exch_id if exch_id else None,
                "portfolio_setup": portfolio_setup if exch_id else False
            }
            
        except Exception as e:
            logger.error(f"Error creating book: {e}")
            return {
                "success": False,
                "error": f"Error creating book: {str(e)}"
            }

    async def _setup_user_portfolio(self, user_id: str, exch_id: str, initial_capital: float) -> bool:
        """Setup user portfolio in exchange system"""
        try:
            # Check if user already exists on this exchange
            user_exists = await self.user_repository.user_exists_on_exchange(user_id, exch_id)
            if user_exists:
                logger.info(f"User {user_id} already exists on exchange {exch_id}")
                # Update capital if different
                await self.user_repository.update_user_capital(user_id, initial_capital)
                return True
            
            # Create new exchange user setup
            success = await self.user_repository.create_exchange_user(user_id, exch_id, initial_capital)
            if success:
                logger.info(f"Successfully setup user portfolio for {user_id} on exchange {exch_id}")
                return True
            else:
                logger.error(f"Failed to setup user portfolio for {user_id} on exchange {exch_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error setting up user portfolio: {e}")
            return False
            
    async def get_books(self, user_id: str) -> Dict[str, Any]:
        """
        Get all books for a user and convert to new format with contract information
        """
        logger.info(f"Getting books for user {user_id}")
        
        try:
            # Get books from repository (in internal format)
            books_internal = await self.book_repository.get_books_by_user(user_id)
            
            # Convert each book to new format
            books = []
            for book_internal in books_internal:
                book = await self._convert_internal_to_new_format(book_internal)
                books.append(book)
            
            logger.info(f"Retrieved {len(books)} books for user {user_id}")
            
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
        Get a single book by ID and convert to new format with contract information
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
            
            # Convert to new format
            book = await self._convert_internal_to_new_format(book_internal)
            
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

    async def _convert_internal_to_new_format(self, book_internal: Dict[str, Any]) -> Dict[str, Any]:
        """Convert internal book format to new API format"""
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
                elif category == 'Position Type':
                    if value == 'Long':
                        book['positionTypes']['long'] = True
                    elif value == 'Short':
                        book['positionTypes']['short'] = True
                elif category == 'Initial Capital':
                    try:
                        book['initialCapital'] = float(value)
                    except (ValueError, TypeError):
                        book['initialCapital'] = 0
                elif category == 'Conviction':
                    if subcategory == 'Levels':
                        try:
                            conviction_schema['levels'] = json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            conviction_schema['levels'] = []
                    elif subcategory == 'Horizons':
                        try:
                            conviction_schema['horizons'] = json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            conviction_schema['horizons'] = []
        
        # Add conviction schema if it has data
        if conviction_schema:
            book['convictionSchema'] = conviction_schema
        
        logger.debug(f"Converted book {book_internal['book_id']} to new format: {book}")
        return book

    async def update_book(self, book_id: str, book_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Update a book with new format and blockchain contract update
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
            position_types = book_data.get('positionTypes', {})
            if position_types.get('long', False):
                parameters.append(["Position Type", "", "Long"])
            if position_types.get('short', False):
                parameters.append(["Position Type", "", "Short"])
            
            # Add initial capital parameter
            if 'initialCapital' in book_data:
                parameters.append(["Initial Capital", "", str(book_data['initialCapital'])])
            
            # Add conviction schema if provided
            if 'convictionSchema' in book_data:
                conviction_schema = book_data['convictionSchema']
                
                # Levels (array)
                if 'levels' in conviction_schema and isinstance(conviction_schema['levels'], list):
                    parameters.append(["Conviction", "Levels", json.dumps(conviction_schema['levels'])])
                
                # Horizons (array)
                if 'horizons' in conviction_schema and isinstance(conviction_schema['horizons'], list):
                    parameters.append(["Conviction", "Horizons", json.dumps(conviction_schema['horizons'])])
            
            # Update in repository
            updated_book_dict = {
                'book_id': book_id,
                'user_id': user_id,
                'parameters': parameters
            }
            
            success = await self.book_repository.update_book(book_id, updated_book_dict)
            
            if not success:
                return {
                    "success": False,
                    "error": "Failed to update book in database"
                }
            
            # Update smart contract
            logger.info(f"Updating smart contract for book {book_id}")
            contract_result = await self.crypto_manager.update_contract(user_id, book_id, updated_book_dict)
            
            if not contract_result.get("success"):
                logger.warning(f"Failed to update contract for book {book_id}: {contract_result.get('error')}")
                # Don't fail the update since database was successful
            
            logger.info(f"Book {book_id} updated successfully")
            
            return {
                "success": True,
                "message": "Book updated successfully"
            }
            
        except Exception as e:
            logger.error(f"Error updating book {book_id}: {e}")
            return {
                "success": False,
                "error": f"Error updating book: {str(e)}"
            }

    async def delete_book(self, book_id: str, user_id: str, force: bool = False) -> Dict[str, Any]:
        """
        Delete a book with blockchain contract cleanup
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
            if book['user_id'] != user_id:
                return {
                    "success": False,
                    "error": "Book does not belong to this user"
                }
            
            # Delete smart contract first
            logger.info(f"Deleting smart contract for book {book_id}")
            contract_result = await self.crypto_manager.delete_contract(user_id, book_id, force)
            
            if not contract_result.get("success") and not force:
                logger.error(f"Failed to delete contract for book {book_id}: {contract_result.get('error')}")
                return {
                    "success": False,
                    "error": f"Failed to delete contract: {contract_result.get('error')}"
                }
            
            # Delete from repository
            success = await self.book_repository.delete_book(book_id)
            
            if not success:
                return {
                    "success": False,
                    "error": "Failed to delete book from database"
                }
            
            logger.info(f"Book {book_id} deleted successfully")
            
            return {
                "success": True,
                "message": "Book deleted successfully"
            }
            
        except Exception as e:
            logger.error(f"Error deleting book {book_id}: {e}")
            return {
                "success": False,
                "error": f"Error deleting book: {str(e)}"
            }

    async def get_contract_details(self, book_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get contract details for a book
        """
        logger.info(f"Getting contract details for book {book_id}, user {user_id}")
        
        try:
            # First verify book ownership
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
            
            # Get contract details from crypto manager
            contract_data = await self.crypto_manager.get_contract_details(user_id, book_id)
            
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