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
        """Handle book creation endpoint with new data format"""
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

        book_id = str(uuid.uuid4())
        logger.info(f"Generated new book ID: {book_id}")

        # Prepare book data with the new format including conviction schema
        book_data = {
            'book_id': book_id,
            'user_id': user_id,
            'name': data.get('name', ''),
            'regions': data.get('regions', []),
            'markets': data.get('markets', []),
            'instruments': data.get('instruments', []),
            'investmentApproaches': data.get('investmentApproaches', []),
            'investmentTimeframes': data.get('investmentTimeframes', []),
            'sectors': data.get('sectors', []),
            'positionTypes': data.get('positionTypes', {'long': False, 'short': False}),
            'initialCapital': data.get('initialCapital', 0),
            'convictionSchema': data.get('convictionSchema', {})
        }

        # Create book
        result = await self.book_manager.create_book(book_data, user_id)
        logger.debug(f"Book manager returned result: {result}")

        if not result["success"]:
            logger.error(f"Book creation failed: {result.get('error', 'Unknown error')}")
            return self.create_error_response(result.get('error', "Failed to create book in database"), 500)

        logger.info(f"Book created successfully with ID: {result['book_id']}")
        return self.create_success_response({"bookId": result["book_id"]})

    async def _get_books(self, request: web.Request) -> web.Response:
        """Handle books retrieval endpoint"""
        # Authenticate request
        auth_success, auth_result = await self.authenticate(request)
        if not auth_success:
            return self.create_error_response(auth_result["error"], auth_result["status"])

        user_id = auth_result["user_id"]
        logger.info(f"Getting books for user {user_id}")

        # Retrieve books
        result = await self.book_manager.get_books(user_id)

        if not result["success"]:
            return self.create_error_response(result.get("error", "Failed to retrieve books"), 500)

        # Return books directly
        return self.create_success_response({"books": result["books"]})

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

        logger.info(f"Getting book {book_id} for user {user_id}")

        # Retrieve book
        result = await self.book_manager.get_book(book_id, user_id)

        if not result["success"]:
            return self.create_error_response(result.get("error", "Book not found or does not belong to user"), 404)

        # Return book directly
        return self.create_success_response({"book": result["book"]})

    async def _update_book(self, request: web.Request) -> web.Response:
        """Handle book update endpoint with new format"""
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

        logger.info(f"Updating book {book_id} for user {user_id}")
        logger.debug(f"Update data: {data}")

        # Prepare book data with the new format
        book_data = {
            'book_id': book_id,
            'user_id': user_id
        }
        
        # Include provided fields in the update
        for field in ['name', 'regions', 'markets', 'instruments', 
                    'investmentApproaches', 'investmentTimeframes', 
                    'sectors', 'positionTypes', 'initialCapital', 'convictionSchema']:
            if field in data:
                book_data[field] = data[field]

        # Update book
        result = await self.book_manager.update_book(book_id, book_data, user_id)

        if not result["success"]:
            return self.create_error_response(result.get("error", "Failed to update book"), 500)

        return self.create_success_response({"message": "Book updated successfully"})