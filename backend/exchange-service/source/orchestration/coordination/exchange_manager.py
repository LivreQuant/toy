# source/orchestration/coordination/exchange_manager.py
import logging
from typing import Dict, List, Optional
from datetime import datetime
from threading import RLock
import threading
import asyncio

from source.config import app_config
from source.orchestration.coordination.book_context import BookContext, initialize_book_context
from source.orchestration.coordination.metadata_handler import (
    load_metadata_from_file, load_metadata_from_postgres, parse_last_snap, parse_market_hours, get_file_timestamp_str
)
from source.orchestration.coordination.gap_detection import detect_gap, load_missing_data
from source.orchestration.coordination.market_data_processing import (
    process_market_data_with_replay_awareness,
    process_queued_live_data,
    process_normal_market_data
)
from source.utils.timezone_utils import ensure_utc, to_iso_string

from source.orchestration.replay.replay_manager import ReplayManager
from source.db.db_manager import DatabaseManager

class ExchangeGroupManager:
    """Manages multiple bookrs in a single exchange group - ALL TIMES IN UTC"""

    def __init__(self, exch_id: str):
        self.exch_id = exch_id
        self.logger = logging.getLogger(self.__class__.__name__)
        self._lock = RLock()

        # Core state
        self.metadata = None
        self.book_contexts: Dict[str, BookContext] = {}
        self.last_snap_time: Optional[datetime] = None
        self.exchange_timezone = None
        self.exchanges = None
        self.market_hours_utc = None
        self._original_last_snap_str: Optional[str] = None
        self.replay_manager = None

        # Parameter storage
        self.book_parameters: Dict[str, Dict] = {}

    async def initialize(self) -> bool:
        """Initialize the exchange group from metadata"""
        try:
            self.logger.info("🔍 Loading metadata...")

            # Load metadata based on environment
            if app_config.is_production:
                self.logger.info("🔄 PRODUCTION MODE: Loading metadata from PostgreSQL")
                self.metadata = await load_metadata_from_postgres(self.exch_id)
            else:
                self.logger.info("🔄 DEVELOPMENT MODE: Loading metadata from JSON file")
                self.metadata = load_metadata_from_file()

            self.logger.info("✅ Metadata loaded successfully")

            # Extract key information
            self.exchange_timezone = self.metadata['timezone']
            self.exchanges = self.metadata['exchanges']

            # Parse last snap time to UTC
            self.last_snap_time, self._original_last_snap_str = parse_last_snap(self.metadata)

            # Convert market hours from exchange timezone to UTC
            self.market_hours_utc = parse_market_hours(
                self.metadata, self.exchange_timezone, self.last_snap_time
            )

            # Load book-specific PM operational parameters
            await self._load_book_parameters()

            # Initialize book contexts
            for book_id, book_config in self.metadata['books'].items():
                book_context = initialize_book_context(
                    book_id, book_config, self.last_snap_time, self.market_hours_utc
                )
                self.book_contexts[book_id] = book_context
                self.logger.info(f"EXCHANGE OBJECT IN EXCHANGE MANAGER: {id(book_context.app_state.exchange)}")

            self.logger.info(f"✅ Exchange group {self.exch_id} initialized with {len(self.book_contexts)} books")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize exchange group: {e}")
            return False

    def check_and_handle_market_data_gap(self, incoming_market_time: datetime):
        """Check for gaps between market timestamps"""
        return detect_gap(self.last_snap_time, incoming_market_time, self.replay_manager)

    async def _load_book_parameters(self):
        """Load PM operational parameters for all books"""
        try:
            db_manager = DatabaseManager()
            await db_manager.initialize()

            for book_id in self.metadata['books'].keys():
                book_params = await db_manager.load_book_operational_parameters(book_id)

                if not book_params:
                    self.logger.warning(f"No PM parameters found for book {book_id}, creating defaults")
                    await db_manager.book_operational_parameters.create_default_parameters_for_book(book_id)
                    book_params = await db_manager.load_book_operational_parameters(book_id)

                self.book_parameters[book_id] = book_params
                self.logger.info(f"✅ Loaded PM operational parameters for book {book_id}")

        except Exception as e:
            self.logger.error(f"❌ Failed to load book PM parameters: {e}")
            raise

    def get_book_parameters(self, book_id: str) -> Dict:
        """Get PM operational parameters for a specific book"""
        return self.book_parameters.get(book_id, {})

    def get_all_book_parameters(self) -> Dict[str, Dict]:
        """Get PM operational parameters for all books"""
        return self.book_parameters

    def load_missing_market_data(self, gap_start: datetime, gap_end: datetime):
        """Load missing market data for the gap period"""
        return load_missing_data(gap_start, gap_end, self.replay_manager)

    def get_file_timestamp_str(self) -> str:
        """Get timestamp string for file operations"""
        return get_file_timestamp_str(self._original_last_snap_str, self.last_snap_time)

    def get_all_books(self) -> List[str]:
        return list(self.book_contexts.keys())

    def get_book_context(self, book_id: str) -> Optional[BookContext]:
        return self.book_contexts.get(book_id)

    def get_metadata(self) -> dict:
        return self.metadata

    def update_last_snap_time(self, market_timestamp: datetime):
        """Update the last snapshot time with MARKET timestamp and persist to database"""
        self.last_snap_time = ensure_utc(market_timestamp)
        if self.metadata:
            new_timestamp_str = to_iso_string(self.last_snap_time)
            self.metadata['last_snap'] = self.last_snap_time
            self._original_last_snap_str = new_timestamp_str

        # Persist to database in production mode
        if app_config.is_production and self.metadata:

            def persist_in_background():

                # Create new database manager for this thread
                db_manager = DatabaseManager()

                async def do_persist():
                    try:
                        await db_manager.initialize()
                        success = await db_manager.metadata.update_exchange_metadata(self.metadata)
                        if success:
                            self.logger.info(f"✅ Database metadata updated for exch_id: {self.exch_id}")
                        else:
                            self.logger.error(f"❌ Database metadata update failed for exch_id: {self.exch_id}")
                    except Exception as e:
                        self.logger.error(f"❌ Database metadata update error: {e}")
                    finally:
                        await db_manager.close()

                # Run in new event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(do_persist())
                finally:
                    loop.close()

            # Run in background thread
            threading.Thread(target=persist_in_background, daemon=True).start()

    async def _persist_metadata_to_database(self):
        """Persist the current metadata to database (async helper method)"""
        try:
            from source.db.db_manager import db_manager

            # Use the existing database manager's metadata manager
            success = await db_manager.metadata.update_exchange_metadata(self.metadata)

            if success:
                self.logger.info(f"✅ Successfully persisted metadata to database for exch_id: {self.exch_id}")
            else:
                self.logger.error(f"❌ Failed to persist metadata to database for exch_id: {self.exch_id}")

        except Exception as e:
            self.logger.error(f"❌ Error persisting metadata to database: {e}")


class EnhancedExchangeGroupManager(ExchangeGroupManager):
    """Enhanced Exchange Group Manager with unified replay mode support"""

    def __init__(self, exch_id: str):
        super().__init__(exch_id)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.unified_replay_manager: Optional[ReplayManager] = None
        self.replay_queue: List = []
        self.live_data_queue: List = []

    def set_replay_manager(self, replay_manager: ReplayManager):
        """Set the unified replay manager"""
        self.unified_replay_manager = replay_manager
        self.replay_manager = replay_manager
        self.logger.info(f"🎬 Replay manager set for exchange group: {self.exch_id}")

    def process_market_data_with_replay_awareness(self, equity_bars: List, fx: Optional[List] = None) -> bool:
        """Process market data with unified replay mode awareness"""
        return process_market_data_with_replay_awareness(
            equity_bars, fx, self.unified_replay_manager,
            self.last_snap_time, self.live_data_queue
        )

    def process_queued_live_data(self):
        """Process queued live data after replay is complete"""
        process_queued_live_data(self.live_data_queue, self.unified_replay_manager)

    def process_replay_market_data(self, equity_bars: List, fx: Optional[List], timestamp: datetime):
        """Process market data specifically for unified replay mode"""
        success = process_normal_market_data(equity_bars, fx, self.unified_replay_manager)
        if success:
            self.update_last_snap_time(timestamp)
        return success

    def is_replay_mode_active(self) -> bool:
        return self.unified_replay_manager and self.unified_replay_manager.is_in_replay_mode()

    def get_replay_status(self) -> dict:
        if self.unified_replay_manager:
            return self.unified_replay_manager.get_replay_status()
        return {'state': 'not_available', 'progress': None, 'is_in_replay': False}