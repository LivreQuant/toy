# source/storage/storage_interface.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from datetime import datetime
import logging
import os
import csv


class StorageInterface(ABC):
    """Abstract interface for storage operations"""

    @abstractmethod
    async def write_data(self, data: List[Dict[str, Any]], table_name: str,
                         user_id: str, timestamp: datetime) -> bool:
        """Write data to storage"""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if storage is available"""
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize storage"""
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup storage resources"""
        pass


class FileStorageHandler(StorageInterface):
    """File-based storage handler"""

    def __init__(self, base_directory: str):
        self.base_directory = base_directory
        self.logger = logging.getLogger(self.__class__.__name__)

    async def write_data(self, data: List[Dict[str, Any]], table_name: str,
                         user_id: str, timestamp: datetime) -> bool:
        """Write data to CSV files"""
        if not data:
            return True

        try:
            # Create user-specific directory
            user_data_dir = os.path.join(self.base_directory, f"USER_{user_id}", table_name)
            os.makedirs(user_data_dir, exist_ok=True)

            # Generate filename with timestamp
            try:
                from source.orchestration.app_state.state_manager import app_state
                current_timestamp = app_state.get_next_timestamp() if app_state else timestamp
            except (ImportError, AttributeError):
                current_timestamp = timestamp

            filename = current_timestamp.strftime('%Y%m%d_%H%M.csv')
            filepath = os.path.join(user_data_dir, filename)

            # Write CSV file
            with open(filepath, 'w', newline='') as f:
                if data:
                    writer = csv.DictWriter(f, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)

            self.logger.info(f"📁 Wrote {len(data)} records to {filepath}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error writing to file: {e}")
            raise Exception(f"File storage write failed: {e}")

    async def is_available(self) -> bool:
        """Check if file storage is available"""
        try:
            os.makedirs(self.base_directory, exist_ok=True)
            return True
        except Exception:
            return False

    async def initialize(self) -> None:
        """Initialize file storage"""
        os.makedirs(self.base_directory, exist_ok=True)
        self.logger.info(f"📁 File storage initialized at {self.base_directory}")

    async def cleanup(self) -> None:
        """Cleanup file storage resources"""
        pass


class DatabaseStorageHandler(StorageInterface):
    """Database-based storage handler"""

    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    async def write_data(self, data: List[Dict[str, Any]], table_name: str,
                         user_id: str, timestamp: datetime) -> bool:
        """Write data to database"""
        if not data:
            return True

        try:
            rows_inserted = await self.db_manager.insert_simulation_data(
                table_name, data, user_id, timestamp
            )
            self.logger.info(f"💾 Inserted {rows_inserted} records into {table_name}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Database write error for {table_name}: {e}")
            raise Exception(f"Database storage write failed: {e}")

    async def is_available(self) -> bool:
        """Check if database is available"""
        return self.db_manager.connected

    async def initialize(self) -> None:
        """Initialize database storage"""
        await self.db_manager.initialize()
        self.logger.info("💾 Database storage initialized")

    async def cleanup(self) -> None:
        """Cleanup database resources"""
        await self.db_manager.close()


class StorageManager:
    """Simple storage manager - no fallback bullshit"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.storage: StorageInterface = None
        self._initialized = False

    async def initialize(self):
        """Initialize storage based on configuration"""
        if self._initialized:
            return

        from source.config import app_config
        from source.db.db_manager import db_manager

        if app_config.use_database_storage:
            self.storage = DatabaseStorageHandler(db_manager)
        else:
            self.storage = FileStorageHandler(app_config.data_directory)

        await self.storage.initialize()
        self._initialized = True
        self.logger.info("✅ Storage manager initialized")

    async def write_data(self, data: List[Dict[str, Any]], table_name: str,
                         user_id: str, timestamp: datetime) -> bool:
        """Write data - throw error if it fails"""
        if not self._initialized:
            await self.initialize()

        if not await self.storage.is_available():
            raise Exception("Storage is not available")

        return await self.storage.write_data(data, table_name, user_id, timestamp)

    async def cleanup(self):
        """Cleanup storage resources"""
        if self.storage:
            await self.storage.cleanup()


# Global storage manager instance
storage_manager = StorageManager()