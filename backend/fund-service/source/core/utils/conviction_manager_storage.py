# source/core/conviction_manager_storage.py
import logging
import os
import csv
import time
import json
import io
from typing import Optional

from minio import Minio
from minio.error import S3Error

logger = logging.getLogger('storage_manager')

class StorageManager:
    """Manager for MinIO file storage operations"""

    def __init__(self):
        """Initialize MinIO client for file storage"""
        self.minio_client = None
        self.bucket_name = None
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

    async def store_research_file(self, file_data: bytes, filename: str, 
                                  fund_id: str, book_id: str, tx_id: str) -> Optional[str]:
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

    async def store_notes_file(self, notes: str, fund_id: str, book_id: str, tx_id: str) -> Optional[str]:
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

    async def store_convictions_csv(self, convictions: list, fund_id: str, 
                                  book_id: str, tx_id: str) -> Optional[str]:
        """Store convictions data as CSV file in MinIO with proper structure"""
        if not self.minio_client:
            logger.warning("MinIO client not available, skipping CSV storage")
            return None
            
        try:
            # Generate file path: fund_id/book_id/tx_id/convictions.csv
            file_path = f"{fund_id}/{book_id}/{tx_id}/convictions.csv"
            
            # Generate CSV content as a simple string first
            if not convictions:
                csv_string = "instrumentId,side,score,participationRate,tag,convictionId\n"
            else:
                # Build CSV manually
                lines = ["instrumentId,side,score,participationRate,tag,convictionId"]
                for conviction in convictions:
                    line = f"{conviction.get('instrumentId','')},{conviction.get('side','')},{conviction.get('score','')},{conviction.get('participationRate','')},{conviction.get('tag','')},{conviction.get('convictionId','')}"
                    lines.append(line)
                csv_string = "\n".join(lines)
            
            logger.info(f"CSV content length: {len(csv_string)}")
            
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
            
            logger.info(f"Successfully stored CSV file: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error storing CSV file: {e}")
            return None

    async def store_cancellation_csv(self, conviction_ids: list, fund_id: str, 
                                   book_id: str, tx_id: str) -> Optional[str]:
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

    async def store_encoded_data(self, book_id: str, encoded_convictions: str, 
                               encoded_research: str, notes: str, user_id: str, 
                               operation: str) -> Optional[str]:
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