# source/api/rest/conviction_controller.py
import logging
import json
import os
import csv
import time
import uuid
from aiohttp import web
from aiohttp.web import FileField

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
        
        # Create uploads directory if it doesn't exist
        self.uploads_dir = os.path.join(os.getcwd(), 'uploads')
        os.makedirs(self.uploads_dir, exist_ok=True)

    async def submit_convictions(self, request: web.Request) -> web.Response:
        """Handle conviction submission endpoint with multipart support"""
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
        """Handle conviction cancellation endpoint with multipart support"""
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
        """Handle multipart conviction submission with file upload"""
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
            research_file_path = None
            
            # Process multipart fields
            async for field in reader:
                if field.name == 'bookId':
                    book_id = await field.text()
                    
                elif field.name == 'convictions':
                    convictions_data = await field.text()
                    try:
                        convictions_json = json.loads(convictions_data)
                        if not isinstance(convictions_json, list):
                            return self.create_error_response("Convictions must be an array", 400)
                    except json.JSONDecodeError:
                        return self.create_error_response("Invalid JSON in convictions field", 400)
                        
                elif field.name == 'notes':
                    notes = await field.text()
                    
                elif field.name == 'researchFile':
                    if isinstance(field, FileField):
                        research_file_path = await self._save_uploaded_file(field, user_id, book_id, 'research')
            
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

            # Store convictions as CSV
            csv_path = await self._store_convictions_csv(convictions_json, user_id, book_id, 'submit')
            
            # Process convictions with additional metadata
            submission_data = {
                'book_id': book_id,
                'convictions': convictions_json,
                'notes': notes,
                'research_file_path': research_file_path,
                'csv_path': csv_path
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

        # Store encoded data
        encoded_data_path = await self._store_encoded_data(
            book_id, encoded_convictions, encoded_research_file, notes, user_id, 'submit'
        )

        # Process encoded submission
        submission_data = {
            'book_id': book_id,
            'encoded_convictions': encoded_convictions,
            'encoded_research_file': encoded_research_file,
            'notes': notes,
            'encoded_data_path': encoded_data_path
        }
        
        result = await self.oconviction_manager.submit_encoded_convictions(submission_data, user_id)
        return web.json_response(result)

    async def _cancel_convictions(self, request: web.Request) -> web.Response:
        """Handle multipart conviction cancellation with file upload"""
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
            research_file_path = None
            
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
                    if isinstance(field, FileField):
                        research_file_path = await self._save_uploaded_file(field, user_id, book_id, 'research')
            
            # Validate required fields
            if not book_id:
                return self.create_error_response("Book ID is required", 400)
                
            if not conviction_ids:
                return self.create_error_response("Convictions IDs are required", 400)
                
            if len(conviction_ids) == 0:
                return self.create_error_response("No conviction IDs provided", 400)

            if len(conviction_ids) > 100:
                return self.create_error_response("Too many convictions. Maximum of 100 cancellations allowed per batch.", 400)

            # Validate book ownership
            book_validation = await self.conviction_manager.validate_book_ownership(book_id, user_id)
            if not book_validation.get('valid'):
                return self.create_error_response(book_validation.get('error', 'Invalid book ID'), 403)

            # Store cancellation data as CSV
            csv_path = await self._store_cancellation_csv(conviction_ids, user_id, book_id)
            
            # Process cancellations with additional metadata
            cancellation_data = {
                'book_id': book_id,
                'conviction_ids': conviction_ids,
                'notes': notes,
                'research_file_path': research_file_path,
                'csv_path': csv_path
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

        # Store encoded data
        encoded_data_path = await self._store_encoded_data(
            book_id, encoded_conviction_ids, encoded_research_file, notes, user_id, 'cancel'
        )

        # Process encoded cancellation
        cancellation_data = {
            'book_id': book_id,
            'encoded_conviction_ids': encoded_conviction_ids,
            'encoded_research_file': encoded_research_file,
            'notes': notes,
            'encoded_data_path': encoded_data_path
        }
        
        result = await self.conviction_manager.cancel_encoded_convictions(cancellation_data, user_id)
        return web.json_response(result)

    async def _save_uploaded_file(self, field: FileField, user_id: str, book_id: str, file_type: str) -> str:
        """Save uploaded file to local storage organized by user and book"""
        # Create user and book specific directory structure
        user_book_dir = os.path.join(self.uploads_dir, user_id, book_id or 'unknown')
        os.makedirs(user_book_dir, exist_ok=True)
        
        # Generate unique filename
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{file_type}_{timestamp}_{unique_id}_{field.filename}"
        file_path = os.path.join(user_book_dir, filename)
        
        try:
            # Save file
            with open(file_path, 'wb') as f:
                while True:
                    chunk = await field.read_chunk(8192)
                    if not chunk:
                        break
                    f.write(chunk)
            
            logger.info(f"Saved uploaded file for book {book_id}: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error saving uploaded file: {e}")
            # Clean up partial file
            if os.path.exists(file_path):
                os.remove(file_path)
            raise

    async def _store_convictions_csv(self, convictions: list, user_id: str, book_id: str, operation: str) -> str:
        """Store convictions data as CSV file organized by user and book"""
        # Create user and book specific directory structure
        user_book_dir = os.path.join(self.uploads_dir, user_id, book_id)
        os.makedirs(user_book_dir, exist_ok=True)
        
        # Generate filename
        timestamp = int(time.time())
        filename = f"convictions_{operation}_{timestamp}.csv"
        csv_path = os.path.join(user_book_dir, filename)
        
        try:
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                if convictions:
                    # Get all unique keys from all convictions (handles dynamic properties)
                    all_keys = set()
                    for conviction in convictions:
                        all_keys.update(conviction.keys())
                    
                    # Sort fieldnames for consistency, put common fields first
                    common_fields = ['instrumentId', 'side', 'quantity', 'score', 'zscore', 'targetPercent', 'targetNotional', 'participationRate', 'tag', 'orderId']
                    other_fields = sorted([k for k in all_keys if k not in common_fields])
                    fieldnames = [f for f in common_fields if f in all_keys] + other_fields
                    
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    
                    # Write header
                    writer.writeheader()
                    
                    # Write convictions
                    for conviction in convictions:
                        writer.writerow(conviction)
            
            logger.info(f"Stored {len(convictions)} convictions CSV for book {book_id}: {csv_path}")
            return csv_path
            
        except Exception as e:
            logger.error(f"Error storing convictions CSV: {e}")
            # Clean up partial file
            if os.path.exists(csv_path):
                os.remove(csv_path)
            raise

    async def _store_cancellation_csv(self, conviction_ids: list, user_id: str, book_id: str) -> str:
        """Store cancellation data as CSV file organized by user and book"""
        # Create user and book specific directory structure
        user_book_dir = os.path.join(self.uploads_dir, user_id, book_id)
        os.makedirs(user_book_dir, exist_ok=True)
        
        # Generate filename
        timestamp = int(time.time())
        filename = f"cancellations_{timestamp}.csv"
        csv_path = os.path.join(user_book_dir, filename)
        
        try:
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow(['conviction_id'])
                
                # Write conviction IDs
                for conviction_id in conviction_ids:
                    writer.writerow([conviction_id])
            
            logger.info(f"Stored cancellation CSV for {len(conviction_ids)} convictions in book {book_id}: {csv_path}")
            return csv_path
            
        except Exception as e:
            logger.error(f"Error storing cancellation CSV: {e}")
            # Clean up partial file
            if os.path.exists(csv_path):
                os.remove(csv_path)
            raise

    async def _store_encoded_data(self, book_id: str, encoded_convictions: str, encoded_research: str, 
                                 notes: str, user_id: str, operation: str) -> str:
        """Store encoded data as JSON file organized by user and book"""
        # Create user and book specific directory structure
        user_book_dir = os.path.join(self.uploads_dir, user_id, book_id)
        os.makedirs(user_book_dir, exist_ok=True)
        
        # Generate filename
        timestamp = int(time.time())
        filename = f"encoded_{operation}_{timestamp}.json"
        file_path = os.path.join(user_book_dir, filename)
        
        try:
            encoded_data = {
                'operation': operation,
                'timestamp': timestamp,
                'user_id': user_id,
                'book_id': book_id,
                'convictions': encoded_convictions,
                'research_file': encoded_research,
                'notes': notes
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(encoded_data, f, indent=2)
            
            logger.info(f"Stored encoded data for book {book_id}: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error storing encoded data: {e}")
            # Clean up partial file
            if os.path.exists(file_path):
                os.remove(file_path)
            raise