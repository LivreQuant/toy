# source/api/rest/book_controller.py
import logging
import uuid
import time
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
        Handle order submission endpoint - Only batch submission is supported
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
        Handle order submission endpoint - Only batch submission is supported
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
        Handle order submission endpoint - Only batch submission is supported
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
        Handle order submission endpoint - Only batch submission is supported
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


    # In book_controller.py - updated _create_book method with enhanced logging
    async def _create_book(self, request: web.Request) -> web.Response:
        """Handle book creation endpoint"""
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

        book_id = uuid.uuid4()
        logger.info(f"Generated new book ID: {book_id}")

        # Convert incoming data to book model format
        book_data = {
            'book_id': str(book_id),
            'user_id': user_id,
            'name': data['name'],
            'parameters': data.get('parameters'),
            'created_at': time.time(),
            'updated_at': time.time()
        }
        
        logger.debug(f"Prepared book data structure: {book_data}")

        # Create book in database
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

        # Retrieve books for this user
        result = await self.book_manager.get_books(user_id)

        if not result["success"]:
            return self.create_error_response(result["error"], 500)

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

        # Retrieve book
        result = await self.book_manager.get_book(book_id, user_id)

        if not result:
            return self.create_error_response("Book not found or does not belong to user", 404)

        return self.create_success_response({"book": result["book"]})


    async def _update_book(self, request: web.Request) -> web.Response:
        """Handle book update endpoint"""
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
        if not existing_book:
            return self.create_error_response("Book not found or does not belong to user", 404)

        # Update only provided fields
        update_data = {}
        if 'name' in data:
            update_data['name'] = data['name']
        if 'parameters' in data:
            update_data['parameters'] = data['parameters']

        # Add updated timestamp
        update_data['updated_at'] = time.time()

        # Update book in database
        success = await self.book_manager.update_book(book_id, update_data, user_id)

        if not success:
            return self.create_error_response("Failed to update book in database", 500)

        return self.create_success_response()

