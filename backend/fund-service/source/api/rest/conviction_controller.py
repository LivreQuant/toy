# source/api/rest/conviction_controller.py
import logging
import json
from aiohttp import web

from source.api.rest.base_controller import BaseController
from source.core.state_manager import StateManager
from source.core.session_manager import SessionManager
from source.core.conviction_manager import ConvictionManager

logger = logging.getLogger('rest_controllers')

class ConvictionController(BaseController):
    """Controller for conviction-related REST endpoints"""

    def __init__(self,
                 state_manager: StateManager,
                 session_manager: SessionManager,
                 conviction_manager: ConvictionManager):
        """Initialize controller with dependencies"""
        super().__init__(session_manager)
        self.state_manager = state_manager
        self.conviction_manager = conviction_manager

    async def submit_convictions(self, request: web.Request) -> web.Response:
        """Handle conviction submission endpoint with file storage"""
        acquired = await self.state_manager.acquire()
        if not acquired:
            return self.create_error_response("Service is currently busy. Please try again later.", 503)

        try:
            return await self._submit_convictions(request)
        except Exception as e:
            logger.error(f"Error handling conviction submission: {e}")
            return self.create_error_response("Server error processing conviction")
        finally:
            await self.state_manager.release()

    async def submit_convictions_encoded(self, request: web.Request) -> web.Response:
        """Handle encoded conviction submission endpoint"""
        acquired = await self.state_manager.acquire()
        if not acquired:
            return self.create_error_response("Service is currently busy. Please try again later.", 503)

        try:
            return await self._submit_convictions_encoded(request)
        except Exception as e:
            logger.error(f"Error handling encoded conviction submission: {e}")
            return self.create_error_response("Server error processing encoded conviction")
        finally:
            await self.state_manager.release()

    async def cancel_convictions(self, request: web.Request) -> web.Response:
        """Handle conviction cancellation endpoint with file storage"""
        acquired = await self.state_manager.acquire()
        if not acquired:
            return self.create_error_response("Service is currently busy. Please try again later.", 503)

        try:
            return await self._cancel_convictions(request)
        except Exception as e:
            logger.error(f"Error handling conviction cancellation: {e}")
            return self.create_error_response("Server error processing cancellation")
        finally:
            await self.state_manager.release()

    async def cancel_convictions_encoded(self, request: web.Request) -> web.Response:
        """Handle encoded conviction cancellation endpoint"""
        acquired = await self.state_manager.acquire()
        if not acquired:
            return self.create_error_response("Service is currently busy. Please try again later.", 503)

        try:
            return await self._cancel_convictions_encoded(request)
        except Exception as e:
            logger.error(f"Error handling encoded conviction cancellation: {e}")
            return self.create_error_response("Server error processing encoded cancellation")
        finally:
            await self.state_manager.release()

    async def _submit_convictions(self, request: web.Request) -> web.Response:
        """Handle multipart conviction submission"""
        # Authenticate request
        auth_success, auth_result = await self.authenticate(request)
        if not auth_success:
            return self.create_error_response(auth_result["error"], auth_result["status"])

        user_id = auth_result["user_id"]
        logger.info(f"Processing conviction submission for user {user_id}")

        try:
            reader = await request.multipart()
            
            book_id = None
            convictions_json = None
            notes = ""
            research_file_data = None
            research_file_name = None
            
            # Process multipart fields
            async for field in reader:
                logger.info(f"Processing field: {field.name}, type: {type(field)}")
                
                if field.name == 'bookId':
                    book_id = await field.text()
                    logger.info(f"Got bookId: {book_id}")
                    
                elif field.name == 'convictions':
                    convictions_data = await field.text()
                    logger.info(f"Got convictions data length: {len(convictions_data)}")
                    try:
                        convictions_json = json.loads(convictions_data)
                        if not isinstance(convictions_json, list):
                            return self.create_error_response("Convictions must be an array", 400)
                    except json.JSONDecodeError:
                        return self.create_error_response("Invalid JSON in convictions field", 400)
                        
                elif field.name == 'notes':
                    notes = await field.text()
                    logger.info(f"Got notes: {notes}")
                    
                elif field.name == 'researchFile':
                    if hasattr(field, 'filename') and field.filename:
                        research_file_data = await field.read()
                        research_file_name = field.filename
                        logger.info(f"Got research file: {research_file_name}, size: {len(research_file_data)} bytes")
                    else:
                        logger.warning(f"researchFile field has no filename")

                else:
                    logger.warning(f"Unknown field: {field.name}")
            
            # Validate required fields
            if not book_id:
                return self.create_error_response("Book ID is required", 400)
                
            if not convictions_json:
                return self.create_error_response("Convictions data is required", 400)
                
            if len(convictions_json) == 0:
                return self.create_error_response("No convictions provided", 400)

            # Validate book ownership
            book_validation = await self.conviction_manager.validate_book_ownership(book_id, user_id)
            if not book_validation.get('valid'):
                return self.create_error_response(book_validation.get('error', 'Invalid book ID'), 403)

            # Process convictions with additional metadata
            submission_data = {
                'book_id': book_id,
                'convictions': convictions_json,
                'notes': notes,
                'research_file_data': research_file_data,
                'research_file_name': research_file_name
            }

            result = await self.conviction_manager.submit_convictions(submission_data, user_id)
            return web.json_response(result)
            
        except Exception as e:
            logger.error(f"Error processing multipart submission: {e}")
            return self.create_error_response("Error processing file upload", 500)
    
    async def _submit_convictions_encoded(self, request: web.Request) -> web.Response:
        """Handle encoded conviction submission"""
        # Authenticate request
        auth_success, auth_result = await self.authenticate(request)
        if not auth_success:
            return self.create_error_response(auth_result["error"], auth_result["status"])

        user_id = auth_result["user_id"]

        # Parse request body
        parse_success, data = await self.parse_json_body(request)
        if not parse_success:
            return self.create_error_response(data["error"], data["status"])

        # Extract required fields
        book_id = data.get('bookId', '')
        encoded_convictions = data.get('convictions', '')
        encoded_research_file = data.get('researchFile', '')
        notes = data.get('notes', '')

        # Validate required fields
        if not book_id:
            return self.create_error_response("Book ID is required", 400)
            
        if not encoded_convictions:
            return self.create_error_response("Encoded convictions data is required", 400)

        # Validate book ownership
        book_validation = await self.conviction_manager.validate_book_ownership(book_id, user_id)
        if not book_validation.get('valid'):
            return self.create_error_response(book_validation.get('error', 'Invalid book ID'), 403)

        # Process encoded submission
        submission_data = {
            'book_id': book_id,
            'encoded_convictions': encoded_convictions,
            'encoded_research_file': encoded_research_file,
            'notes': notes
        }
        
        result = await self.conviction_manager.submit_encoded_convictions(submission_data, user_id)
        return web.json_response(result)

    async def _cancel_convictions(self, request: web.Request) -> web.Response:
        """Handle multipart conviction cancellation"""
        # Authenticate request
        auth_success, auth_result = await self.authenticate(request)
        if not auth_success:
            return self.create_error_response(auth_result["error"], auth_result["status"])

        user_id = auth_result["user_id"]

        try:
            reader = await request.multipart()
            
            book_id = None
            conviction_ids = None
            notes = ""
            research_file_data = None
            research_file_name = None
            
            # Process multipart fields
            async for field in reader:
                if field.name == 'bookId':
                    book_id = await field.text()
                    
                elif field.name == 'convictionIds':
                    conviction_ids_data = await field.text()
                    try:
                        conviction_ids = json.loads(conviction_ids_data)
                        if not isinstance(conviction_ids, list):
                            return self.create_error_response("Conviction IDs must be an array", 400)
                    except json.JSONDecodeError:
                        return self.create_error_response("Invalid JSON in convictionIds field", 400)
                        
                elif field.name == 'notes':
                    notes = await field.text()
                    
                elif field.name == 'researchFile':
                    if hasattr(field, 'filename') and field.filename:
                        research_file_data = await field.read()
                        research_file_name = field.filename
                        logger.info(f"Got research file: {research_file_name}, size: {len(research_file_data)} bytes")
                else:
                    logger.warning(f"Unknown multipart field: {field.name}")
            
            # Validate required fields
            if not book_id:
                return self.create_error_response("Book ID is required", 400)
                
            if not conviction_ids:
                return self.create_error_response("Conviction IDs are required", 400)
                
            if len(conviction_ids) == 0:
                return self.create_error_response("No conviction IDs provided", 400)

            if len(conviction_ids) > 100:
                return self.create_error_response("Too many convictions. Maximum of 100 cancellations allowed per batch.", 400)

            # Validate book ownership
            book_validation = await self.conviction_manager.validate_book_ownership(book_id, user_id)
            if not book_validation.get('valid'):
                return self.create_error_response(book_validation.get('error', 'Invalid book ID'), 403)

            # Process cancellations
            cancellation_data = {
                'book_id': book_id,
                'conviction_ids': conviction_ids,
                'notes': notes,
                'research_file_data': research_file_data,
                'research_file_name': research_file_name
            }
            
            result = await self.conviction_manager.cancel_convictions(cancellation_data, user_id)
            return web.json_response(result)
            
        except Exception as e:
            logger.error(f"Error processing multipart cancellation: {e}")
            return self.create_error_response("Error processing file upload", 500)

    async def _cancel_convictions_encoded(self, request: web.Request) -> web.Response:
        """Handle encoded conviction cancellation"""
        # Authenticate request
        auth_success, auth_result = await self.authenticate(request)
        if not auth_success:
            return self.create_error_response(auth_result["error"], auth_result["status"])

        user_id = auth_result["user_id"]

        # Parse request body
        parse_success, data = await self.parse_json_body(request)
        if not parse_success:
            return self.create_error_response(data["error"], data["status"])

        # Extract required fields
        book_id = data.get('bookId', '')
        encoded_conviction_ids = data.get('convictionIds', '')
        encoded_research_file = data.get('researchFile', '')
        notes = data.get('notes', '')

        # Validate required fields
        if not book_id:
            return self.create_error_response("Book ID is required", 400)
            
        if not encoded_conviction_ids:
            return self.create_error_response("Encoded conviction IDs are required", 400)

        # Validate book ownership
        book_validation = await self.conviction_manager.validate_book_ownership(book_id, user_id)
        if not book_validation.get('valid'):
            return self.create_error_response(book_validation.get('error', 'Invalid book ID'), 403)

        # Process encoded cancellation
        cancellation_data = {
            'book_id': book_id,
            'encoded_conviction_ids': encoded_conviction_ids,
            'encoded_research_file': encoded_research_file,
            'notes': notes
        }
        
        result = await self.conviction_manager.cancel_encoded_convictions(cancellation_data, user_id)
        return web.json_response(result)