# source/simulation/managers/utils.py
import asyncio
import csv
import logging
import os
import traceback
import queue
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import RLock, Thread
from typing import Dict, List, Optional, Callable, Any, TypeVar, Generic

from source.db.db_manager import DatabaseManager

# Global database queue instance
_db_queue = None
T = TypeVar('T')


class DatabaseQueue:
    """Handles async database writes in a separate thread"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._queue = queue.Queue()
        self._shutdown = False
        self._worker_thread = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="DBWriter")
        self.start_worker()

    def start_worker(self):
        """Start the database worker thread"""
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._worker_thread = Thread(target=self._worker_loop, daemon=True)
            self._worker_thread.start()
            self.logger.info("🔄 Database worker thread started")

    def _worker_loop(self):
        """Main worker loop for processing database writes"""
        # Create event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Initialize database manager
        db_manager = None
        try:
            db_manager = DatabaseManager()
            loop.run_until_complete(db_manager.initialize())
            self.logger.info("✅ Database worker initialized successfully")
        except Exception as e:
            self.logger.error(f"❌ Database worker initialization failed: {e}")
            return

        while not self._shutdown:
            try:
                # Get item from queue with timeout
                try:
                    item = self._queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                if item is None:  # Shutdown signal
                    break

                table_name, data, book_id, timestamp = item

                # Process the database write
                try:
                    loop.run_until_complete(self._write_to_database(db_manager, table_name, data, book_id, timestamp))
                    self.logger.info(f"✅ Successfully wrote {len(data)} records to {table_name}")
                except Exception as e:
                    self.logger.error(f"❌ Database write error for {table_name}: {e}")
                    self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
                finally:
                    self._queue.task_done()

            except Exception as e:
                self.logger.error(f"❌ Worker thread error: {e}")

        # Cleanup
        if db_manager:
            try:
                loop.run_until_complete(db_manager.close())
            except Exception as e:
                self.logger.error(f"❌ Error closing database: {e}")

        loop.close()

    async def _write_to_database(self, db_manager: 'DatabaseManager', table_name: str, data: List[Dict], book_id: str,
                                 timestamp: datetime):
        """Write data to database using the manager"""
        if not db_manager.connected:
            raise Exception("Database not connected")

        # Use the centralized insert method
        result = await db_manager.insert_simulation_data(table_name, data, book_id, timestamp)
        return result

    def enqueue_write(self, table_name: str, data: List[Dict], book_id: str, timestamp: datetime):
        """Enqueue a database write operation"""
        if not self._shutdown:
            self.logger.debug(f"🔄 Enqueuing {len(data)} records for {table_name}")
            self._queue.put((table_name, data, book_id, timestamp))

    def shutdown(self):
        """Shutdown the database queue"""
        self.logger.info("🔄 Shutting down database queue...")
        self._shutdown = True
        self._queue.put(None)  # Signal worker to stop

        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)

        self._executor.shutdown(wait=True)
        self.logger.info("✅ Database queue shutdown complete")


def get_database_queue():
    """Get or create the global database queue"""
    global _db_queue
    if _db_queue is None:
        _db_queue = DatabaseQueue()
    return _db_queue


class TrackingManager:
    """Base class for managers that track data"""

    def __init__(self, manager_name: str, table_name: str, headers: List[str], tracking: bool = False):
        self.manager_name = manager_name
        self.table_name = table_name
        self.headers = headers
        self.tracking = tracking
        self._lock = RLock()
        self.logger = logging.getLogger(f"{self.__class__.__name__}.{manager_name}")

        # Store current book_id context for database writes
        self._current_book_id: Optional[str] = None

        # Initialize database queue if using database storage
        from source.config import app_config
        if app_config.use_database_storage:
            global _db_queue
            _db_queue = get_database_queue()

        # Initialize file path for development mode
        self.csv_file = None
        if not app_config.use_database_storage:
            self._init_csv_file()

    def set_book_context(self, book_id: str) -> None:
        """Set the current book context for this manager instance"""
        self._current_book_id = book_id
        self.logger.debug(f"📋 {self.manager_name} book context set to: {book_id}")

    def _init_csv_file(self):
        """Initialize CSV file for development mode"""
        try:
            data_dir = self._get_book_data_dir()
            if data_dir:
                self.csv_file = os.path.join(data_dir, f"{self.table_name}.csv")
                if not os.path.exists(self.csv_file):
                    with open(self.csv_file, 'w', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=self.headers)
                        writer.writeheader()
        except Exception as e:
            self.logger.error(f"Error initializing CSV file: {e}")

    def _get_book_data_dir(self) -> Optional[str]:
        """Get book-specific data directory"""
        try:
            from source.config import app_config
            book_id = self._get_current_book_id()

            if book_id and hasattr(app_config, 'data_directory') and app_config.data_directory:
                book_data_dir = os.path.join(app_config.data_directory, f"BOOK_{book_id}", self.table_name)
                os.makedirs(book_data_dir, exist_ok=True)
                return book_data_dir
        except Exception as e:
            self.logger.warning(f"Could not create book data directory: {e}")

        return None

    def write_to_storage(self, data: List[Dict], timestamp: Optional[datetime] = None):
        """Write data to storage (database or file based on config)"""
        # Check tracking flag first - if false, don't record anything
        if not self.tracking:
            return

        if not data:
            return

        # Get the correct book ID from app_state
        book_id = self._get_current_book_id()

        from source.config import app_config

        # Route based on environment: Production = Database, Development = Files
        if app_config.use_database_storage:
            # Production mode: Write to database only
            self._queue_database_write(data, timestamp, book_id)
            self.logger.debug(f"📤 DATABASE: Queued {len(data)} {self.table_name} records")
        else:
            # Development mode: Write to file only
            self._write_to_file(data)
            self.logger.debug(f"📁 FILE: Wrote {len(data)} {self.table_name} records")

    def _queue_database_write(self, data: List[Dict], timestamp: Optional[datetime], book_id: str):
        """Queue database write operation"""
        try:
            global _db_queue
            if _db_queue is None:
                _db_queue = get_database_queue()
            _db_queue.enqueue_write(self.table_name, data, book_id, timestamp or datetime.now())
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

    def _get_current_book_id(self) -> str:
        """Get the current book ID from stored context or app_state"""
        # First try stored book context
        if self._current_book_id:
            self.logger.debug(f"📍 Using {self.manager_name} book context: {self._current_book_id}")
            return self._current_book_id

        # Fallback to app_state
        try:
            from source.orchestration.app_state.state_manager import app_state
            book_id = app_state.get_book_id()
            self.logger.debug(f"📍 Got book ID from app_state: {book_id}")
            if book_id:
                return book_id
        except Exception as e:
            self.logger.warning(f"⚠️ Error getting book ID from app_state: {e}")

        # Final fallback - raise error
        self.logger.error(f"❌ No book context available in {self.manager_name}")
        raise ValueError(f"No book context available for database write in {self.manager_name}")

    def get_status(self) -> Dict[str, Any]:
        """Get status information for this manager"""
        return {
            'manager_name': self.manager_name,
            'table_name': self.table_name,
            'tracking': self.tracking,
            'book_context': self._current_book_id,
            'csv_file': self.csv_file
        }

    def reset(self):
        """Reset manager to initial state"""
        with self._lock:
            self._current_book_id = None
            self.logger.info(f"🔄 {self.manager_name} reset to initial state")

    def validate(self) -> Dict[str, Any]:
        """Validate manager configuration"""
        validation = {
            'valid': True,
            'errors': [],
            'warnings': []
        }

        if not self.headers:
            validation['valid'] = False
            validation['errors'].append("No headers defined")

        if not self.table_name:
            validation['valid'] = False
            validation['errors'].append("No table name defined")

        if self.tracking and not self._current_book_id:
            validation['warnings'].append("Tracking enabled but no book context set")

        return validation

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

    def register_callback(self, callback: Callable[[T], None]) -> None:
        """Register a callback function"""
        if callback not in self._callbacks:
            self._callbacks.append(callback)
            self.logger.debug(f"📞 Registered callback: {callback.__name__}")

    def unregister_callback(self, callback: Callable[[T], None]) -> None:
        """Unregister a callback function"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            self.logger.debug(f"📞 Unregistered callback: {callback.__name__}")

    def _notify_callbacks(self, data: T) -> None:
        """Notify all registered callbacks"""
        for callback in self._callbacks:
            try:
                callback(data)
            except Exception as e:
                self.logger.error(f"❌ Error in callback {callback.__name__}: {e}")

    def clear_callbacks(self) -> None:
        """Clear all registered callbacks"""
        self._callbacks.clear()
        self.logger.debug("📞 All callbacks cleared")

    def get_callback_count(self) -> int:
        """Get number of registered callbacks"""
        return len(self._callbacks)


class DataProcessor(ABC):
    """Abstract base class for data processors"""

    def __init__(self, processor_name: str):
        self.processor_name = processor_name
        self.logger = logging.getLogger(f"{self.__class__.__name__}.{processor_name}")

    @abstractmethod
    def process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process the input data and return processed data"""
        pass

    @abstractmethod
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """Validate the input data"""
        pass

    def get_processor_info(self) -> Dict[str, str]:
        """Get processor information"""
        return {
            'name': self.processor_name,
            'type': self.__class__.__name__
        }


class StateMachine:
    """Simple state machine for manager states"""

    def __init__(self, initial_state: str, valid_transitions: Dict[str, List[str]]):
        self.current_state = initial_state
        self.valid_transitions = valid_transitions
        self.state_history: List[tuple] = [(initial_state, datetime.now())]
        self.logger = logging.getLogger(self.__class__.__name__)

    def transition_to(self, new_state: str) -> bool:
        """Transition to a new state if valid"""
        if new_state in self.valid_transitions.get(self.current_state, []):
            old_state = self.current_state
            self.current_state = new_state
            self.state_history.append((new_state, datetime.now()))
            self.logger.info(f"🔄 State transition: {old_state} -> {new_state}")
            return True
        else:
            self.logger.warning(f"⚠️ Invalid state transition: {self.current_state} -> {new_state}")
            return False

    def can_transition_to(self, new_state: str) -> bool:
        """Check if transition to new state is valid"""
        return new_state in self.valid_transitions.get(self.current_state, [])

    def get_state_history(self) -> List[tuple]:
        """Get complete state history"""
        return self.state_history.copy()

    def reset_to_initial(self, initial_state: str) -> None:
        """Reset to initial state"""
        self.current_state = initial_state
        self.state_history = [(initial_state, datetime.now())]
        self.logger.info(f"🔄 Reset to initial state: {initial_state}")


class EventBus:
    """Simple event bus for inter-manager communication"""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)
        self._lock = RLock()

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """Subscribe to an event type"""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []

            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)
                self.logger.debug(f"📡 Subscribed to {event_type}: {callback.__name__}")

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Unsubscribe from an event type"""
        with self._lock:
            if event_type in self._subscribers and callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
                self.logger.debug(f"📡 Unsubscribed from {event_type}: {callback.__name__}")

    def publish(self, event_type: str, event_data: Any) -> None:
        """Publish an event to all subscribers"""
        with self._lock:
            if event_type in self._subscribers:
                for callback in self._subscribers[event_type]:
                    try:
                        callback(event_data)
                    except Exception as e:
                        self.logger.error(f"❌ Error in event callback for {event_type}: {e}")

    def clear_subscribers(self, event_type: Optional[str] = None) -> None:
        """Clear subscribers for specific event type or all"""
        with self._lock:
            if event_type:
                self._subscribers.pop(event_type, None)
                self.logger.debug(f"📡 Cleared subscribers for {event_type}")
            else:
                self._subscribers.clear()
                self.logger.debug("📡 Cleared all subscribers")

    def get_subscriber_count(self, event_type: str) -> int:
        """Get number of subscribers for an event type"""
        with self._lock:
            return len(self._subscribers.get(event_type, []))


class PerformanceMonitor:
    """Monitor performance metrics for managers"""

    def __init__(self, manager_name: str):
        self.manager_name = manager_name
        self.logger = logging.getLogger(f"{self.__class__.__name__}.{manager_name}")
        self._metrics: Dict[str, List[float]] = {}
        self._lock = RLock()

    def record_metric(self, metric_name: str, value: float) -> None:
        """Record a performance metric"""
        with self._lock:
            if metric_name not in self._metrics:
                self._metrics[metric_name] = []

            self._metrics[metric_name].append(value)

            # Keep only last 1000 measurements to prevent memory growth
            if len(self._metrics[metric_name]) > 1000:
                self._metrics[metric_name] = self._metrics[metric_name][-1000:]

    def get_metric_stats(self, metric_name: str) -> Dict[str, float]:
        """Get statistics for a metric"""
        with self._lock:
            if metric_name not in self._metrics or not self._metrics[metric_name]:
                return {}

            values = self._metrics[metric_name]
            return {
                'count': len(values),
                'min': min(values),
                'max': max(values),
                'avg': sum(values) / len(values),
                'latest': values[-1]
            }

    def get_all_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get statistics for all metrics"""
        with self._lock:
            return {metric: self.get_metric_stats(metric) for metric in self._metrics.keys()}

    def clear_metrics(self, metric_name: Optional[str] = None) -> None:
        """Clear metrics"""
        with self._lock:
            if metric_name:
                self._metrics.pop(metric_name, None)
            else:
                self._metrics.clear()


class ResourceManager:
    """Manage resources like memory and file handles"""

    def __init__(self, manager_name: str):
        self.manager_name = manager_name
        self.logger = logging.getLogger(f"{self.__class__.__name__}.{manager_name}")
        self._resources: Dict[str, Any] = {}
        self._lock = RLock()

    def acquire_resource(self, resource_name: str, resource: Any) -> None:
        """Acquire a resource"""
        with self._lock:
            if resource_name in self._resources:
                self.logger.warning(f"⚠️ Resource {resource_name} already exists, replacing")

            self._resources[resource_name] = resource
            self.logger.debug(f"🔧 Acquired resource: {resource_name}")

    def release_resource(self, resource_name: str) -> bool:
        """Release a resource"""
        with self._lock:
            if resource_name in self._resources:
                resource = self._resources.pop(resource_name)

                # Try to clean up the resource
                if hasattr(resource, 'close'):
                    try:
                        resource.close()
                    except Exception as e:
                        self.logger.error(f"❌ Error closing resource {resource_name}: {e}")

                self.logger.debug(f"🔧 Released resource: {resource_name}")
                return True

            return False

    def get_resource(self, resource_name: str) -> Optional[Any]:
        """Get a resource"""
        with self._lock:
            return self._resources.get(resource_name)

    def release_all_resources(self) -> None:
        """Release all resources"""
        with self._lock:
            resource_names = list(self._resources.keys())
            for resource_name in resource_names:
                self.release_resource(resource_name)

            self.logger.info(f"🔧 Released all resources for {self.manager_name}")

    def get_resource_count(self) -> int:
        """Get number of active resources"""
        with self._lock:
            return len(self._resources)


class ConfigurationManager:
    """Manage configuration for managers"""

    def __init__(self, manager_name: str, default_config: Dict[str, Any] = None):
        self.manager_name = manager_name
        self.logger = logging.getLogger(f"{self.__class__.__name__}.{manager_name}")
        self._config = default_config or {}
        self._lock = RLock()

    def set_config(self, key: str, value: Any) -> None:
        """Set a configuration value"""
        with self._lock:
            self._config[key] = value
            self.logger.debug(f"⚙️ Config set: {key} = {value}")

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        with self._lock:
            return self._config.get(key, default)

    def update_config(self, config_dict: Dict[str, Any]) -> None:
        """Update multiple configuration values"""
        with self._lock:
            self._config.update(config_dict)
            self.logger.debug(f"⚙️ Config updated with {len(config_dict)} values")

    def get_all_config(self) -> Dict[str, Any]:
        """Get all configuration"""
        with self._lock:
            return self._config.copy()

    def reset_config(self, default_config: Dict[str, Any] = None) -> None:
        """Reset configuration to defaults"""
        with self._lock:
            self._config = default_config or {}
            self.logger.info(f"⚙️ Configuration reset for {self.manager_name}")

    def validate_config(self, required_keys: List[str]) -> Dict[str, Any]:
        """Validate configuration has required keys"""
        with self._lock:
            validation = {
                'valid': True,
                'missing_keys': [],
                'present_keys': list(self._config.keys())
            }

            for key in required_keys:
                if key not in self._config:
                    validation['valid'] = False
                    validation['missing_keys'].append(key)

            return validation