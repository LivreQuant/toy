# source/simulation/managers/utils.py
import os
import logging
import csv
import threading
import queue
import time
import asyncio
import asyncpg
from typing import Callable, List, TypeVar, Generic, Dict, Optional, Any
from datetime import datetime

T = TypeVar('T')


class DatabaseWriteQueue:
    """Thread-safe queue for database write operations with proper async handling"""

    def __init__(self, max_queue_size: int = 1000):
        self.queue = queue.Queue(maxsize=max_queue_size)
        self.shutdown_flag = threading.Event()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        self.logger = logging.getLogger(self.__class__.__name__)

    def _worker(self):
        """Background worker thread for database writes with dedicated event loop"""
        # Create a dedicated event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Import here to ensure we're in the right thread context
        try:
            from source.db.db_manager import DatabaseManager
            from source.config import app_config

            # Create a thread-local database manager instance
            thread_db_manager = DatabaseManager()

            # Initialize the connection pool in this thread's loop
            loop.run_until_complete(thread_db_manager.initialize())

            while not self.shutdown_flag.is_set():
                try:
                    # Get item from queue with timeout
                    item = self.queue.get(timeout=1.0)

                    if item is None:  # Shutdown signal
                        break

                    self._process_database_write(item, loop, thread_db_manager)
                    self.queue.task_done()

                except queue.Empty:
                    continue
                except Exception as e:
                    self.logger.error(f"❌ Database worker error: {e}", exc_info=True)

            # Clean up
            loop.run_until_complete(thread_db_manager.close())

        except Exception as e:
            self.logger.error(f"❌ Database worker initialization failed: {e}", exc_info=True)
        finally:
            loop.close()

    def _process_database_write(self, item, loop, thread_db_manager):
        """Process a single database write operation in the worker thread"""
        try:
            table_name, data, user_id, timestamp = item

            # Run the async database operation in this thread's loop
            coro = thread_db_manager.insert_simulation_data(table_name, data, user_id, timestamp)
            result = loop.run_until_complete(coro)

            if result > 0:
                self.logger.debug(f"✅ Inserted {result} records into '{table_name}' for user '{user_id}'")

        except Exception as e:
            self.logger.error(f"❌ Database write failed for table '{item[0]}': {e}", exc_info=True)

    def enqueue_write(self, table_name: str, data: List[Dict], user_id: str, timestamp: datetime):
        """Enqueue a database write operation"""
        try:
            if self.queue.full():
                self.logger.warning(f"⚠️ Database queue full, dropping write for {table_name}")
                return

            self.queue.put((table_name, data, user_id, timestamp), block=False)

        except queue.Full:
            self.logger.warning(f"⚠️ Failed to queue database write for {table_name}")

    def shutdown(self):
        """Shutdown the database writer"""
        self.shutdown_flag.set()
        self.queue.put(None)  # Shutdown signal

        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5.0)


# Global database queue instance
_db_queue = DatabaseWriteQueue()


class TrackingManager:
    """Base class for all tracking managers with file and database persistence"""

    def __init__(self, manager_name: str, table_name: str, headers: List[str], tracking: bool = False):
        self.manager_name = manager_name
        self.table_name = table_name
        self.headers = headers
        self.tracking = tracking
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f"{manager_name}.TrackingManager")

        # Initialize storage based on environment
        from source.config import app_config

        # File tracking setup for development
        if not app_config.use_database_storage:
            self._setup_file_tracking()

    def _setup_file_tracking(self):
        """Setup CSV file for tracking"""
        try:
            from source.config import app_config

            # Use data_directory instead of output_dir
            output_dir = os.path.join(app_config.data_directory, "simulation_results")
            os.makedirs(output_dir, exist_ok=True)

            # Setup CSV file path
            self.csv_file = os.path.join(output_dir, f"{self.table_name}.csv")

            # Write headers if file doesn't exist
            if not os.path.exists(self.csv_file):
                with open(self.csv_file, 'w', newline='') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=self.headers)
                    writer.writeheader()

        except Exception as e:
            self.logger.error(f"❌ Error setting up file tracking: {e}")

    def write_to_storage(self, data: List[Dict], timestamp: Optional[datetime] = None):
        """Write data to storage - routes based on tracking flag and environment"""

        # Check tracking flag first - if false, don't record anything
        if not self.tracking:
            return

        if not data:
            return

        # Get the correct user ID from app_state
        user_id = self._get_current_user_id()

        from source.config import app_config

        # Route based on environment: Production = Database, Development = Files
        if app_config.use_database_storage:
            # Production mode: Write to database only
            self._queue_database_write(data, timestamp, user_id)
            self.logger.debug(f"📤 DATABASE: Queued {len(data)} {self.table_name} records")
        else:
            # Development mode: Write to file only
            self._write_to_file(data)
            self.logger.debug(f"📁 FILE: Wrote {len(data)} {self.table_name} records")

    def _queue_database_write(self, data: List[Dict], timestamp: Optional[datetime], user_id: str):
        """Queue database write operation"""
        try:
            _db_queue.enqueue_write(self.table_name, data, user_id, timestamp or datetime.now())
        except Exception as e:
            self.logger.error(f"❌ Database queue error: {e}")

    def _write_to_file(self, data: List[Dict]):
        """Write data to CSV file"""
        try:
            with self._lock:
                with open(self.csv_file, 'a', newline='') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=self.headers)
                    writer.writerows(data)
        except Exception as e:
            self.logger.error(f"❌ Error writing to file: {e}")
            raise

    def _get_current_user_id(self) -> str:
        """Get the current user ID from app_state"""
        try:
            from source.orchestration.app_state.state_manager import app_state

            # The user ID is stored as _user_id, not current_user_id!
            if hasattr(app_state, '_user_id') and app_state._user_id:
                user_id = app_state._user_id
                self.logger.debug(f"📍 Got user ID from app_state: {user_id}")
                return user_id
            else:
                self.logger.warning("⚠️ No user ID found in app_state._user_id")

        except Exception as e:
            self.logger.warning(f"⚠️ Error getting user ID from app_state: {e}")

        # Fallback - but this should rarely be used now
        fallback_user_id = 'USER_000'
        self.logger.warning(f"⚠️ Using fallback user ID: {fallback_user_id}")
        return fallback_user_id

    @classmethod
    def shutdown_database_writer(cls):
        """Shutdown the database writer (call this on application exit)"""
        global _db_queue
        if _db_queue:
            _db_queue.shutdown()


class CallbackManager(Generic[T]):
    """Simple callback manager"""

    def __init__(self, manager_name: str = "UnknownManager"):
        self._callbacks: List[Callable[[T], None]] = []
        self.logger = logging.getLogger(f"{self.__class__.__name__}.{manager_name}")
        self.manager_name = manager_name

    def register_callback(self, callback: Callable[[T], None]) -> None:
        """Register a callback"""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[T], None]) -> None:
        """Remove a callback"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def clear_callbacks(self) -> None:
        """Clear all callbacks"""
        self._callbacks.clear()

    def _notify_callbacks(self, data: T) -> None:
        """Notify all callbacks"""
        for callback in self._callbacks:
            try:
                callback(data)
            except Exception as e:
                self.logger.error(f"❌ Callback error: {e}")