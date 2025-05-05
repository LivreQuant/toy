import logging
import json
from aiohttp import web

from source.core.book_manager import BookManager
from source.core.state_manager import StateManager
from source.api.rest.controllers import get_token

logger = logging.getLogger('book_controller')


class BookController:
    """Controller for book-related REST endpoints"""

    def __init__(self, book_manager: BookManager, state_manager: StateManager):
        """Initialize controller with book manager and state manager"""
        self.book_manager = book_manager
        self.state_manager = state_manager

    async def create_book(self, request: web.Request) -> web.Response:
        """Handle book creation endpoint"""
        logger.info("Received create book request")
        
        # Try to acquire the lock first
        acquired = await self.state_manager.acquire()
        if not acquired:
            return web.json_response({
                "success": False,
                "error": "Service is currently busy. Please try again later."
            }, status=503)  # Service Unavailable
        
        try:
            # Extract token and device ID
            token, device_id = get_token(request)
            
            logger.info(f"Token and device ID extracted: device_id={device_id}")

            if not token:
                return web.json_response({
                    "success": False,
                    "error": "Authentication token is required"
                }, status=401)

            # Get user_id from token
            user_id = await self._get_user_id_from_token(token)
            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Invalid authentication token"
                }, status=401)
            
            logger.info(f"User ID from token: {user_id}")

            # Validate device ID
            device_valid = await self.book_manager.validation_manager.validate_device_id(device_id)
            if not device_valid:
                return web.json_response({
                    "success": False,
                    "error": "Invalid device ID for this session"
                }, status=400)
            
            logger.info(f"Device ID validation: {device_valid}")

            # Parse request body
            try:
                data = await request.json()
                logger.info(f"Request body parsed: {data}")
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON in request body"
                }, status=400)

            # Process book creation
            result = await self.book_manager.create_book(data, user_id)
            logger.info(f"Book creation result: {result}")
            
            if result['success']:
                return web.json_response(result)
            else:
                return web.json_response(result, status=400)
        
        except Exception as e:
            logger.error(f"Error in create_book handler: {e}")
            return web.json_response({
                "success": False,
                "error": f"Server error: {str(e)}"
            }, status=500)
        finally:
            # Always release the lock, even if there's an error
            await self.state_manager.release()

    async def get_books(self, request: web.Request) -> web.Response:
        """Handle get all books endpoint"""
        logger.info("Received get books request")
        
        # Extract token and device ID
        token, device_id = get_token(request)
        
        logger.info(f"Token and device ID extracted: device_id={device_id}")

        if not token:
            return web.json_response({
                "success": False,
                "error": "Authentication token is required"
            }, status=401)

        # Get user_id from token
        user_id = await self._get_user_id_from_token(token)
        if not user_id:
            return web.json_response({
                "success": False,
                "error": "Invalid authentication token"
            }, status=401)
        
        logger.info(f"User ID from token: {user_id}")

        # Validate device ID
        device_valid = await self.book_manager.validation_manager.validate_device_id(device_id)
        if not device_valid:
            return web.json_response({
                "success": False,
                "error": "Invalid device ID for this session"
            }, status=400)
        
        logger.info(f"Device ID validation: {device_valid}")

        # Get all books for user
        result = await self.book_manager.get_books(user_id)
        logger.info(f"Get books result: {len(result.get('books', []))} books found")
        
        return web.json_response(result)

    async def get_book(self, request: web.Request) -> web.Response:
        """Handle get book by ID endpoint"""
        # Extract token and device ID
        token, device_id = get_token(request)
        
        # Extract book ID from URL
        book_id = request.match_info.get('book_id')
        logger.info(f"Received get book request: book_id={book_id}")

        if not token:
            return web.json_response({
                "success": False,
                "error": "Authentication token is required"
            }, status=401)

        # Get user_id from token
        user_id = await self._get_user_id_from_token(token)
        if not user_id:
            return web.json_response({
                "success": False,
                "error": "Invalid authentication token"
            }, status=401)

        # Validate device ID
        device_valid = await self.book_manager.validation_manager.validate_device_id(device_id)
        if not device_valid:
            return web.json_response({
                "success": False,
                "error": "Invalid device ID for this session"
            }, status=400)

        if not book_id:
            return web.json_response({
                "success": False,
                "error": "Book ID is required"
            }, status=400)

        # Get book
        result = await self.book_manager.get_book(book_id, user_id)
        
        if result['success']:
            return web.json_response(result)
        else:
            status = 404 if result.get('error') == 'Book not found' else 400
            return web.json_response(result, status=status)

    async def update_book(self, request: web.Request) -> web.Response:
        """Handle update book endpoint"""
        # Try to acquire the lock first
        acquired = await self.state_manager.acquire()
        if not acquired:
            return web.json_response({
                "success": False,
                "error": "Service is currently busy. Please try again later."
            }, status=503)  # Service Unavailable
        
        try:
            # Extract token and device ID
            token, device_id = get_token(request)
            
            # Extract book ID from URL
            book_id = request.match_info.get('book_id')
            logger.info(f"Received update book request: book_id={book_id}")

            if not token:
                return web.json_response({
                    "success": False,
                    "error": "Authentication token is required"
                }, status=401)

            # Get user_id from token
            user_id = await self._get_user_id_from_token(token)
            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Invalid authentication token"
                }, status=401)

            # Validate device ID
            device_valid = await self.book_manager.validation_manager.validate_device_id(device_id)
            if not device_valid:
                return web.json_response({
                    "success": False,
                    "error": "Invalid device ID for this session"
                }, status=400)

            if not book_id:
                return web.json_response({
                    "success": False,
                    "error": "Book ID is required"
                }, status=400)

            # Parse request body
            try:
                data = await request.json()
                logger.info(f"Request body parsed: {data}")
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON in request body"
                }, status=400)

            # Update book
            result = await self.book_manager.update_book(book_id, data, user_id)
            
            if result['success']:
                return web.json_response(result)
            else:
                status = 404 if result.get('error') == 'Book not found' else 400
                return web.json_response(result, status=status)
        
        finally:
            # Always release the lock, even if there's an error
            await self.state_manager.release()

    async def delete_book(self, request: web.Request) -> web.Response:
        """Handle delete book endpoint"""
        # Try to acquire the lock first
        acquired = await self.state_manager.acquire()
        if not acquired:
            return web.json_response({
                "success": False,
                "error": "Service is currently busy. Please try again later."
            }, status=503)  # Service Unavailable
        
        try:
            # Extract token and device ID
            token, device_id = get_token(request)
            
            # Extract book ID from URL
            book_id = request.match_info.get('book_id')
            logger.info(f"Received delete book request: book_id={book_id}")

            if not token:
                return web.json_response({
                    "success": False,
                    "error": "Authentication token is required"
                }, status=401)

            # Get user_id from token
            user_id = await self._get_user_id_from_token(token)
            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Invalid authentication token"
                }, status=401)

            # Validate device ID
            device_valid = await self.book_manager.validation_manager.validate_device_id(device_id)
            if not device_valid:
                return web.json_response({
                    "success": False,
                    "error": "Invalid device ID for this session"
                }, status=400)

            if not book_id:
                return web.json_response({
                    "success": False,
                    "error": "Book ID is required"
                }, status=400)

            # Delete book
            result = await self.book_manager.delete_book(book_id, user_id)
            
            if result['success']:
                return web.json_response(result)
            else:
                status = 404 if result.get('error') == 'Book not found' else 400
                return web.json_response(result, status=status)
        
        finally:
            # Always release the lock, even if there's an error
            await self.state_manager.release()
    
    async def _get_user_id_from_token(self, token: str) -> str:
        """Extract user ID from authentication token"""
        try:
            validation_result = await self.book_manager.validation_manager.auth_client.validate_token(token)

            if not validation_result.get('valid', False):
                logger.warning(f"Invalid authentication token")
                return None

            # Check for both naming conventions (snake_case and camelCase)
            user_id = validation_result.get('user_id') or validation_result.get('userId')
            if not user_id:
                logger.warning("Auth token valid but no user ID returned")
                return None

            return user_id
        except Exception as e:
            logger.error(f"Error extracting user ID from token: {e}")
            return None