# source/api/rest/book_controller.py
import logging
import uuid
from aiohttp import web

from source.api.rest.base_controller import BaseController

from source.core.state_manager import StateManager
from source.core.session_manager import SessionManager
from source.core.book_manager import BookManager

logger = logging.getLogger('book_controllers')

class BookController(BaseController):
    """Controller for book-related REST endpoints"""

    def __init__(self,
                 state_manager: StateManager,
                 session_manager: SessionManager,
                 book_manager: BookManager):
        """Initialize controller with dependencies"""
        super().__init__(session_manager)
        self.state_manager = state_manager
        self.book_manager = book_manager


    async def create_book(self, request: web.Request) -> web.Response:
        """
        Handle book creation endpoint
        """
        # Try to acquire the lock first
        acquired = await self.state_manager.acquire()
        if not acquired:
            return self.create_error_response("Service is currently busy. Please try again later.", 503)

        try:
            return await self._create_book(request)

        except Exception as e:
            logger.error(f"Error handling book creation: {e}")
            return self.create_error_response("Server error processing book creation")
        finally:
            # Always release the lock, even if there's an error
            await self.state_manager.release()


    async def get_books(self, request: web.Request) -> web.Response:
        """
        Handle books retrieval endpoint
        """
        # Try to acquire the lock first
        acquired = await self.state_manager.acquire()
        if not acquired:
            return self.create_error_response("Service is currently busy. Please try again later.", 503)

        try:
            return await self._get_books(request)

        except Exception as e:
            logger.error(f"Error handling books retrieval: {e}")
            return self.create_error_response("Server error processing book request")
        finally:
            # Always release the lock, even if there's an error
            await self.state_manager.release()


    async def get_book(self, request: web.Request) -> web.Response:
        """
        Handle single book retrieval endpoint
        """
        # Try to acquire the lock first
        acquired = await self.state_manager.acquire()
        if not acquired:
            return self.create_error_response("Service is currently busy. Please try again later.", 503)

        try:
            return await self._get_book(request)

        except Exception as e:
            logger.error(f"Error handling book retrieval: {e}")
            return self.create_error_response("Server error processing book request")
        finally:
            # Always release the lock, even if there's an error
            await self.state_manager.release()


    async def update_book(self, request: web.Request) -> web.Response:
        """
        Handle book update endpoint
        """
        # Try to acquire the lock first
        acquired = await self.state_manager.acquire()
        if not acquired:
            return self.create_error_response("Service is currently busy. Please try again later.", 503)

        try:
            return await self._update_book(request)

        except Exception as e:
            logger.error(f"Error handling book update: {e}")
            return self.create_error_response("Server error processing book update")
        finally:
            # Always release the lock, even if there's an error
            await self.state_manager.release()


    async def _create_book(self, request: web.Request) -> web.Response:
        """Handle book creation endpoint using temporal data pattern"""
        # Authenticate request
        logger.info(f"Processing book creation request from {request.remote}")
        auth_success, auth_result = await self.authenticate(request)
        if not auth_success:
            logger.warning(f"Authentication failed: {auth_result['error']}")
            return self.create_error_response(auth_result["error"], auth_result["status"])

        user_id = auth_result["user_id"]
        logger.info(f"Authenticated user {user_id} for book creation")

        # Parse request body
        parse_success, data = await self.parse_json_body(request)
        if not parse_success:
            logger.warning(f"Failed to parse request body: {data['error']}")
            return self.create_error_response(data["error"], data["status"])

        logger.debug(f"Parsed request data: {data}")

        # Validate required fields
        valid_fields, field_error = self.validate_required_fields(data, ['name', 'parameters'])
        if not valid_fields:
            logger.warning(f"Missing required fields: {field_error['error']}")
            return self.create_error_response(field_error["error"], field_error["status"])

        book_id = str(uuid.uuid4())
        logger.info(f"Generated new book ID: {book_id}")

        # Convert incoming data to book model format
        book_data = {
            'book_id': book_id,
            'user_id': user_id,
            'name': data['name'],
            'parameters': data.get('parameters')
        }
        
        logger.debug(f"Prepared book data structure: {book_data}")

        # Create book in database using temporal data pattern
        logger.info(f"Calling book_manager.create_book for user {user_id}")
        result = await self.book_manager.create_book(book_data, user_id)
        logger.debug(f"Book manager returned result: {result}")

        if not result["success"]:
            logger.error(f"Book creation failed: {result.get('error', 'Unknown error')}")
            return self.create_error_response("Failed to create book in database", 500)

        logger.info(f"Book created successfully with ID: {result['book_id']}")
        return self.create_success_response({"bookId": result["book_id"]})

    
    async def _get_books(self, request: web.Request) -> web.Response:
        """Handle books retrieval endpoint"""
        # Authenticate request
        auth_success, auth_result = await self.authenticate(request)
        if not auth_success:
            return self.create_error_response(auth_result["error"], auth_result["status"])

        user_id = auth_result["user_id"]

        # Retrieve active books for this user
        result = await self.book_manager.get_books(user_id)

        if not result["success"]:
            return self.create_error_response(result["error"], 500)

        # Transform the books to use meaningful properties
        books = result["books"]
        transformed_books = []
        
        for book in books:
            transformed_book = {
                "book_id": book["book_id"],
                "user_id": book["user_id"],
                "name": book["name"],
                "status": book["status"],
                "active_at": book["active_at"]
            }
            
            # Convert EAV properties to flat JSON structure matching the client schema
            # Use bookParameters as the source which contains the properly mapped fields
            if 'bookParameters' in book:
                # Create parameters array in the expected format
                parameters = []
                
                # Extract properly mapped fields
                for key, value in book['bookParameters'].items():
                    # Determine category and subcategory based on the property
                    if key == "Region":
                        category, subcategory = "Region", ""
                        parameters.append([category, subcategory, value])
                    elif key == "Market":
                        category, subcategory = "Market", ""
                        parameters.append([category, subcategory, value])
                    elif key == "Instrument":
                        category, subcategory = "Instrument", ""
                        parameters.append([category, subcategory, value])
                    elif key == "Investment Approach":
                        category, subcategory = "Investment Approach", ""
                        parameters.append([category, subcategory, value])
                    elif key == "Investment Timeframe":
                        category, subcategory = "Investment Timeframe", ""
                        parameters.append([category, subcategory, value])
                    elif key == "Sector":
                        category, subcategory = "Sector", ""
                        parameters.append([category, subcategory, value])
                    elif key == "Position.Long":
                        category, subcategory = "Position", "Long"
                        parameters.append([category, subcategory, value])
                    elif key == "Position.Short":
                        category, subcategory = "Position", "Short"
                        parameters.append([category, subcategory, value])
                    elif key == "Allocation":
                        category, subcategory = "Allocation", ""
                        parameters.append([category, subcategory, value])
                    else:
                        # Generic fallback for unknown properties
                        parts = key.split(".")
                        if len(parts) > 1:
                            category, subcategory = parts[0], parts[1]
                        else:
                            category, subcategory = parts[0], ""
                        parameters.append([category, subcategory, value])
                
                transformed_book["parameters"] = parameters
            
            transformed_books.append(transformed_book)

        return self.create_success_response({"books": transformed_books})


    async def _get_book(self, request: web.Request) -> web.Response:
        """Handle single book retrieval endpoint"""
        # Authenticate request
        auth_success, auth_result = await self.authenticate(request)
        if not auth_success:
            return self.create_error_response(auth_result["error"], auth_result["status"])

        user_id = auth_result["user_id"]

        # Get book ID from URL
        book_id = request.match_info.get('id')
        if not book_id:
            return self.create_error_response("Book ID is required", 400)

        # Retrieve active book
        result = await self.book_manager.get_book(book_id, user_id)

        if not result["success"]:
            return self.create_error_response("Book not found or does not belong to user", 404)

        # Transform the book to use meaningful properties
        book = result["book"]
        transformed_book = dict(book)
        
        # Remove the triplet-style parameters if bookParameters exists
        if 'bookParameters' in book:
            # Use the new transformed parameters instead
            if 'parameters' in transformed_book:
                del transformed_book['parameters']

        return self.create_success_response({"book": transformed_book})


    async def _update_book(self, request: web.Request) -> web.Response:
        """Handle book update endpoint using temporal data pattern"""
        # Authenticate request
        auth_success, auth_result = await self.authenticate(request)
        if not auth_success:
            return self.create_error_response(auth_result["error"], auth_result["status"])

        user_id = auth_result["user_id"]

        # Get book ID from URL
        book_id = request.match_info.get('id')
        if not book_id:
            return self.create_error_response("Book ID is required", 400)

        # Parse request body
        parse_success, data = await self.parse_json_body(request)
        if not parse_success:
            return self.create_error_response(data["error"], data["status"])

        # Verify book exists and belongs to user
        existing_book = await self.book_manager.get_book(book_id, user_id)
        if not existing_book["success"]:
            return self.create_error_response("Book not found or does not belong to user", 404)

        # Update only provided fields
        update_data = {}
        if 'name' in data:
            update_data['name'] = data['name']
        if 'parameters' in data:
            update_data['parameters'] = data['parameters']
        if 'bookParameters' in data:
            # Convert bookParameters to parameters
            # This is a reverse transformation to convert the new client format back to DB format
            parameters = []
            for key, value in data['bookParameters'].items():
                # Determine category and subcategory based on key
                # This is a simplified logic - you might need more complex logic based on your app
                if '.' in key:
                    category, subcategory = key.split('.')
                else:
                    # Default categorization - modify as needed
                    if key in ['riskLevel', 'maxDrawdown', 'volatility']:
                        category = 'risk'
                        subcategory = key
                    elif key in ['targetReturns', 'benchmark', 'horizon']:
                        category = 'strategy'
                        subcategory = key
                    else:
                        category = 'general'
                        subcategory = key
                
                # Add to parameters list
                parameters.append([category, subcategory, value])
            
            update_data['parameters'] = parameters

        # No need to include timestamps as they will be managed by the repository
        logger.info(f"Updating book {book_id} with fields: {list(update_data.keys())}")

        # Update book in database using temporal data pattern
        success = await self.book_manager.update_book(book_id, update_data, user_id)

        if not success["success"]:
            return self.create_error_response("Failed to update book in database", 500)

        return self.create_success_response()