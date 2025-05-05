import logging
import json
import time
import uuid
from aiohttp import web

from source.db.book_repository import BookRepository
from source.api.rest.controllers import get_token

logger = logging.getLogger('book_controllers')

class BookController:
    """Controller for book-related REST endpoints"""

    def __init__(self, book_repository, auth_client, validation_manager):
        """Initialize controller with repositories and services"""
        self.book_repository = book_repository
        self.auth_client = auth_client
        self.validation_manager = validation_manager

    async def _get_user_id_from_token(self, token: str, csrf_token: str = None) -> str:
        """Extract user ID from authentication token"""
        try:
            # Use auth_client directly instead of through order_manager
            validation_result = await self.auth_client.validate_token(token, csrf_token)

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
        
    async def create_book(self, request: web.Request) -> web.Response:
        """Handle book creation endpoint"""
        try:
            # Extract token and device ID
            token, device_id, csrf_token = get_token(request)

            if not token:
                return web.json_response({
                    "success": False,
                    "error": "Authentication token is required"
                }, status=401)

            # Get user_id from token
            user_id = await self._get_user_id_from_token(token, csrf_token)
            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Invalid authentication token"
                }, status=401)

            # Validate device ID
            device_valid = await self.validation_manager.validate_device_id(device_id)
            if not device_valid:
                return web.json_response({
                    "success": False,
                    "error": "Invalid device ID for this session"
                }, status=400)

            # Parse request body
            try:
                data = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON in request body"
                }, status=400)

            # Validate required fields
            required_fields = ['name', 'initialCapital', 'riskLevel']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                return web.json_response({
                    "success": False,
                    "error": f"Missing required fields: {', '.join(missing_fields)}"
                }, status=400)

            # Convert incoming data to book model format
            book_data = {
                'book_id': str(uuid.uuid4()),
                'user_id': user_id,
                'name': data['name'],
                'initial_capital': data['initialCapital'],
                'risk_level': data['riskLevel'],
                'market_focus': data.get('marketFocus'),
                'trading_strategy': data.get('tradingStrategy'),
                'max_position_size': data.get('maxPositionSize'),
                'max_total_risk': data.get('maxTotalRisk'),
                'status': 'CONFIGURED',
                'created_at': time.time(),
                'updated_at': time.time()
            }

            # Create book in database
            book_id = await self.book_repository.create_book(book_data)
            
            if not book_id:
                return web.json_response({
                    "success": False,
                    "error": "Failed to create book in database"
                }, status=500)

            return web.json_response({
                "success": True,
                "bookId": book_id
            })

        except Exception as e:
            logger.error(f"Error handling book creation: {e}")
            return web.json_response({
                "success": False,
                "error": "Server error processing book creation"
            }, status=500)

    async def get_books(self, request: web.Request) -> web.Response:
        """Handle books retrieval endpoint"""
        try:
            # Extract token and device ID
            token, device_id, csrf_token = get_token(request)

            if not token:
                return web.json_response({
                    "success": False,
                    "error": "Authentication token is required"
                }, status=401)

            # Get user_id from token
            user_id = await self._get_user_id_from_token(token, csrf_token)
            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Invalid authentication token"
                }, status=401)

            # Validate device ID
            device_valid = await self.validation_manager.validate_device_id(device_id)
            if not device_valid:
                return web.json_response({
                    "success": False,
                    "error": "Invalid device ID for this session"
                }, status=400)

            # Retrieve books for this user
            books = await self.book_repository.get_user_books(user_id)

            return web.json_response({
                "success": True,
                "books": books
            })

        except Exception as e:
            logger.error(f"Error handling books retrieval: {e}")
            return web.json_response({
                "success": False,
                "error": "Server error processing book request"
            }, status=500)

    async def get_book(self, request: web.Request) -> web.Response:
        """Handle single book retrieval endpoint"""
        try:
            # Extract token and device ID
            token, device_id, csrf_token = get_token(request)

            if not token:
                return web.json_response({
                    "success": False,
                    "error": "Authentication token is required"
                }, status=401)

            # Get user_id from token
            user_id = await self._get_user_id_from_token(token, csrf_token)
            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Invalid authentication token"
                }, status=401)

            # Validate device ID
            device_valid = await self.validation_manager.validate_device_id(device_id)
            if not device_valid:
                return web.json_response({
                    "success": False,
                    "error": "Invalid device ID for this session"
                }, status=400)

            # Get book ID from URL
            book_id = request.match_info.get('id')
            if not book_id:
                return web.json_response({
                    "success": False,
                    "error": "Book ID is required"
                }, status=400)

            # Retrieve book
            book = await self.book_repository.get_book(book_id, user_id)
            
            if not book:
                return web.json_response({
                    "success": False,
                    "error": "Book not found or does not belong to user"
                }, status=404)

            return web.json_response({
                "success": True,
                "book": book
            })

        except Exception as e:
            logger.error(f"Error handling book retrieval: {e}")
            return web.json_response({
                "success": False,
                "error": "Server error processing book request"
            }, status=500)

    async def update_book(self, request: web.Request) -> web.Response:
        """Handle book update endpoint"""
        try:
            # Extract token and device ID
            token, device_id, csrf_token = get_token(request)

            if not token:
                return web.json_response({
                    "success": False,
                    "error": "Authentication token is required"
                }, status=401)

            # Get user_id from token
            user_id = await self._get_user_id_from_token(token, csrf_token)
            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Invalid authentication token"
                }, status=401)

            # Validate device ID
            device_valid = await self.validation_manager.validate_device_id(device_id)
            if not device_valid:
                return web.json_response({
                    "success": False,
                    "error": "Invalid device ID for this session"
                }, status=400)

            # Get book ID from URL
            book_id = request.match_info.get('id')
            if not book_id:
                return web.json_response({
                    "success": False,
                    "error": "Book ID is required"
                }, status=400)

            # Parse request body
            try:
                data = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON in request body"
                }, status=400)

            # Verify book exists and belongs to user
            existing_book = await self.book_repository.get_book(book_id, user_id)
            if not existing_book:
                return web.json_response({
                    "success": False,
                    "error": "Book not found or does not belong to user"
                }, status=404)

            # Update only provided fields
            update_data = {}
            if 'name' in data:
                update_data['name'] = data['name']
            if 'initialCapital' in data:
                update_data['initial_capital'] = data['initialCapital']
            if 'riskLevel' in data:
                update_data['risk_level'] = data['riskLevel']
            if 'marketFocus' in data:
                update_data['market_focus'] = data['marketFocus']
            if 'tradingStrategy' in data:
                update_data['trading_strategy'] = data['tradingStrategy']
            if 'maxPositionSize' in data:
                update_data['max_position_size'] = data['maxPositionSize']
            if 'maxTotalRisk' in data:
                update_data['max_total_risk'] = data['maxTotalRisk']
            if 'status' in data:
                update_data['status'] = data['status']

            # Add updated timestamp
            update_data['updated_at'] = time.time()

            # Update book in database
            success = await self.book_repository.update_book(book_id, user_id, update_data)
            
            if not success:
                return web.json_response({
                    "success": False,
                    "error": "Failed to update book in database"
                }, status=500)

            return web.json_response({
                "success": True
            })

        except Exception as e:
            logger.error(f"Error handling book update: {e}")
            return web.json_response({
                "success": False,
                "error": "Server error processing book update"
            }, status=500)