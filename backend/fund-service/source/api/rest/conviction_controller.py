# source/api/rest/conviction_controller.py
import logging
import json
import os
import csv
import time
import uuid
import asyncio
from aiohttp import web
from aiohttp.web import FileField
from minio import Minio
from minio.error import S3Error
import io

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
        
        # Initialize MinIO client
        self._init_minio_client()

    def _init_minio_client(self):
        """Initialize MinIO client for file storage"""
        try:
            # Get MinIO configuration from environment or use defaults
            minio_endpoint = os.getenv('MINIO_ENDPOINT', 'storage-service:9000')
            minio_access_key = os.getenv('MINIO_ACCESS_KEY', 'convictions-storage')
            minio_secret_key = os.getenv('MINIO_SECRET_KEY', 'conviction-storage-secret-2024')
            
            self.minio_client = Minio(
                minio_endpoint,
                access_key=minio_access_key,
                secret_key=minio_secret_key,
                secure=False  # Set to True if using HTTPS
            )
            
            self.bucket_name = os.getenv('MINIO_BUCKET_NAME', 'conviction-files')
            
            # Ensure bucket exists
            self._ensure_bucket_exists()
            
            logger.info(f"MinIO client initialized successfully with endpoint: {minio_endpoint}")
            
        except Exception as e:
            logger.error(f"Failed to initialize MinIO client: {e}")
            self.minio_client = None

    def _ensure_bucket_exists(self):
        """Ensure the bucket exists"""
        try:
            if not self.minio_client.bucket_exists(self.bucket_name):
                self.minio_client.make_bucket(self.bucket_name)
                logger.info(f"Created bucket: {self.bucket_name}")
        except Exception as e:
            logger.error(f"Error ensuring bucket exists: {e}")

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
        """Handle multipart conviction submission with MinIO storage"""
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

            # Store files in MinIO and create CSV
            research_file_path = None
            csv_file_path = None
            
            # Get fund_id first (you'll need to query this)
            fund_id = await self._get_fund_id_for_user(user_id)

            # Create and store CSV file
            csv_file_path = await self._store_convictions_csv(
                convictions_json, user_id, book_id, '0001', fund_id
            )

            # Store research file if provided
            if research_file_data and research_file_name:
                research_file_path = await self._store_research_file(
                    research_file_data, research_file_name, fund_id, book_id, '0001'
                )
                logger.info(f"Stored research file: {research_file_path}")
            else:
                logger.info("No research file provided")

            # Store notes if provided
            if notes and notes.strip():
                notes_file_path = await self._store_notes_file(notes, fund_id, book_id, '0001')
                logger.info(f"Stored notes file: {notes_file_path}")

            # Process convictions with additional metadata
            submission_data = {
                'book_id': book_id,
                'convictions': convictions_json,
                'notes': notes,
                'research_file_path': research_file_path,
                'csv_file_path': csv_file_path
            }

            result = await self.conviction_manager.submit_convictions(submission_data, user_id)
            return web.json_response(result)
            
        except Exception as e:
            logger.error(f"Error processing multipart submission: {e}")
            return self.create_error_response("Error processing file upload", 500)
            
    async def _get_fund_id_for_user(self, user_id: str) -> str:
        """Get fund_id for a user"""
        try:
            # You already have access to fund data through your managers
            # This is a quick database query
            pool = await self.conviction_manager.conviction_repository.db_pool.get_pool()
            async with pool.acquire() as conn:
                fund_id = await conn.fetchval(
                    "SELECT fund_id FROM fund.funds WHERE user_id = $1 LIMIT 1",
                    user_id
                )
                return str(fund_id) if fund_id else user_id  # fallback to user_id
        except Exception as e:
            logger.error(f"Error getting fund_id for user {user_id}: {e}")
            return user_id  # fallback to user_id
    
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
        
        result = await self.conviction_manager.submit_encoded_convictions(submission_data, user_id)
        return web.json_response(result)

    async def _cancel_convictions(self, request: web.Request) -> web.Response:
        """Handle multipart conviction cancellation with file storage"""
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
                    
                elif field.name == 'researchFile' and isinstance(field, FileField):
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

            # Store files
            research_file_path = None
            csv_file_path = None
            
            # Store research file if provided
            if research_file_data and research_file_name:
                research_file_path = await self._store_research_file(
                    research_file_data, research_file_name, user_id, book_id
                )
            
            # Create and store cancellation CSV
            csv_file_path = await self._store_cancellation_csv(conviction_ids, user_id, book_id)
            
            # Process cancellations
            cancellation_data = {
                'book_id': book_id,
                'conviction_ids': conviction_ids,
                'notes': notes,
                'research_file_path': research_file_path,
                'csv_file_path': csv_file_path
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

    async def _store_research_file(self, file_data: bytes, filename: str, 
                                fund_id: str, book_id: str, tx_id: str) -> str:
        """Store research file in MinIO with proper structure"""
        if not self.minio_client:
            logger.warning("MinIO client not available, skipping file storage")
            return None
            
        try:
            # Generate file path: fund_id/book_id/tx_id/research.{extension}
            file_extension = filename.split('.')[-1] if '.' in filename else 'txt'
            file_path = f"{fund_id}/{book_id}/{tx_id}/research.{file_extension}"
            
            # Upload to MinIO
            file_stream = io.BytesIO(file_data)
            self.minio_client.put_object(
                self.bucket_name,
                file_path,
                file_stream,
                length=len(file_data),
                content_type='application/octet-stream'
            )
            
            logger.info(f"Stored research file: {file_path}")
            return file_path
            
        except S3Error as e:
            logger.error(f"Error storing research file in MinIO: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error storing research file: {e}")
            return None

    async def _store_notes_file(self, notes: str, fund_id: str, book_id: str, tx_id: str) -> str:
        """Store notes as text file in MinIO"""
        if not self.minio_client or not notes.strip():
            return None
            
        try:
            # Generate file path: fund_id/book_id/tx_id/notes.txt
            file_path = f"{fund_id}/{book_id}/{tx_id}/notes.txt"
            
            # Convert notes to bytes
            notes_bytes = notes.encode('utf-8')
            notes_stream = io.BytesIO(notes_bytes)
            
            # Upload to MinIO
            self.minio_client.put_object(
                self.bucket_name,
                file_path,
                notes_stream,
                length=len(notes_bytes),
                content_type='text/plain'
            )
            
            logger.info(f"Stored notes file: {file_path}")
            return file_path
            
        except S3Error as e:
            logger.error(f"Error storing notes file in MinIO: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error storing notes file: {e}")
            return None

    async def _store_convictions_csv(self, convictions: list, user_id: str, 
                                book_id: str, tx_id: str, fund_id: str) -> str:
        """Store convictions data as CSV file in MinIO with proper structure"""
        if not self.minio_client:
            logger.warning("MinIO client not available, skipping CSV storage")
            return None
            
        try:
            # Generate file path: fund_id/book_id/tx_id/convictions.csv
            file_path = f"{fund_id}/{book_id}/{tx_id}/convictions.csv"
            
            # DEBUG: Log what we're trying to store
            logger.info(f"Storing {len(convictions)} convictions to {file_path}")
            logger.info(f"First conviction: {convictions[0] if convictions else 'NONE'}")
            
            # Generate CSV content as a simple string first
            if not convictions:
                csv_string = "instrumentId,side,score,participationRate,tag,convictionId\n"
            else:
                # Build CSV manually to debug
                lines = ["instrumentId,side,score,participationRate,tag,convictionId"]
                for conviction in convictions:
                    line = f"{conviction.get('instrumentId','')},{conviction.get('side','')},{conviction.get('score','')},{conviction.get('participationRate','')},{conviction.get('tag','')},{conviction.get('convictionId','')}"
                    lines.append(line)
                csv_string = "\n".join(lines)
            
            logger.info(f"CSV content length: {len(csv_string)}")
            logger.info(f"CSV content preview: {csv_string[:100]}...")
            
            # Convert to bytes
            csv_bytes = csv_string.encode('utf-8')
            
            # Create a fresh BytesIO stream
            data_stream = io.BytesIO(csv_bytes)
            
            # Upload with explicit parameters
            result = self.minio_client.put_object(
                bucket_name=self.bucket_name,
                object_name=file_path,
                data=data_stream,
                length=len(csv_bytes),
                content_type='text/csv'
            )
            
            logger.info(f"MinIO upload result: {result}")
            logger.info(f"Successfully stored CSV file: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error storing CSV file: {e}")
            logger.error(f"Error type: {type(e)}")
            return None

    async def _store_cancellation_csv(self, conviction_ids: list, fund_id: str, book_id: str, tx_id: str) -> str:
        """Store cancellation data as CSV file in MinIO with proper structure"""
        if not self.minio_client:
            logger.warning("MinIO client not available, skipping CSV storage")
            return None
            
        try:
            # Generate file path: fund_id/book_id/tx_id/cancellations.csv
            file_path = f"{fund_id}/{book_id}/{tx_id}/cancellations.csv"
            
            # Generate CSV content
            csv_content = io.StringIO()
            writer = csv.writer(csv_content)
            
            # Write header and data
            writer.writerow(['conviction_id'])
            for conviction_id in conviction_ids:
                writer.writerow([conviction_id])
            
            # Convert to bytes
            csv_bytes = csv_content.getvalue().encode('utf-8')
            csv_stream = io.BytesIO(csv_bytes)
            
            # Upload to MinIO
            self.minio_client.put_object(
                self.bucket_name,
                file_path,
                csv_stream,
                length=len(csv_bytes),
                content_type='text/csv'
            )
            
            logger.info(f"Stored cancellation CSV with {len(conviction_ids)} conviction IDs: {file_path}")
            return file_path
            
        except S3Error as e:
            logger.error(f"Error storing cancellation CSV in MinIO: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error storing cancellation CSV: {e}")
            return None

    async def _store_encoded_data(self, book_id: str, encoded_convictions: str, encoded_research: str, 
                                 notes: str, user_id: str, operation: str) -> str:
        """Store encoded data as JSON file in MinIO"""
        if not self.minio_client:
            logger.warning("MinIO client not available, skipping encoded data storage")
            return None
            
        try:
            # Generate file path
            timestamp = int(time.time())
            file_path = f"encoded/{user_id}/{book_id}/{operation}_{timestamp}.json"
            
            encoded_data = {
                'operation': operation,
                'timestamp': timestamp,
                'user_id': user_id,
                'book_id': book_id,
                'convictions': encoded_convictions,
                'research_file': encoded_research,
                'notes': notes
            }
            
            # Convert to JSON bytes
            json_bytes = json.dumps(encoded_data, indent=2).encode('utf-8')
            json_stream = io.BytesIO(json_bytes)
            
            # Upload to MinIO
            self.minio_client.put_object(
                self.bucket_name,
                file_path,
                json_stream,
                length=len(json_bytes),
                content_type='application/json'
            )
            
            logger.info(f"Stored encoded data for book {book_id}: {file_path}")
            return file_path
            
        except S3Error as e:
            logger.error(f"Error storing encoded data in MinIO: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error storing encoded data: {e}")
            return None