# source/orchestration/coordination/metadata_handler.py
import asyncio
import json
import os
import traceback
import logging
from datetime import datetime

from source.utils.timezone_utils import parse_iso_timestamp
from source.utils.timezone_utils import parse_market_hours_to_utc

# Use standard Python logging initially
logger = logging.getLogger(__name__)


def load_metadata_from_file() -> dict:
    """Load exchange group metadata from JSON file"""
    try:
        print("📂 Loading metadata from JSON file...")

        current_file = os.path.abspath(__file__)
        # Navigate up from source/orchestration/coordination/metadata_handler.py to project root
        data_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
        metadata_file = os.path.join(data_dir, "data", "exchange_group_metadata.json")

        if not os.path.exists(metadata_file):
            raise FileNotFoundError(f"Metadata file not found: {metadata_file}")

        with open(metadata_file, 'r') as f:
            return json.load(f)

    except Exception as e:
        print(f"❌ Error loading metadata from file: {e}")
        raise


async def load_metadata_from_postgres(exch_id: str) -> dict:
    """Load metadata from PostgreSQL (production) - async version"""
    try:
        print(f"🔄 Loading metadata from PostgreSQL for exch_id: {exch_id}")

        # Import here to avoid circular imports
        from source.db.db_manager import db_manager

        print("🔄 Initializing database connection...")
        await db_manager.initialize()
        print("✅ Database connection initialized")

        print(f"🔍 Loading metadata for exch_id: {exch_id}")
        metadata = await db_manager.load_exchange_metadata(exch_id)

        # Validate metadata
        if not metadata:
            print(f"❌ No metadata returned from database for exch_id: {exch_id}")
            raise ValueError(f"No metadata found for exch_id: {exch_id}")

        print(f"✅ PostgreSQL metadata loaded for group: {metadata.get('exch_id', 'UNKNOWN')}")

        # DEBUG: Print all metadata fields and their types
        print("🔍 DEBUG: Metadata fields and types:")
        for key, value in metadata.items():
            print(f"   {key}: {type(value).__name__} = {value}")

        # Get the exch_id from metadata
        exch_id = metadata.get('exch_id')
        if not exch_id:
            raise ValueError("No exch_id found in metadata")

        print(f"🔍 Found exch_id: {exch_id}")

        # Load books for this exchange
        print(f"🔄 Loading books for exch_id: {exch_id}")
        books_data = await db_manager.load_books_for_exchange(exch_id)

        if not books_data:
            print(f"❌ No books found for exch_id: {exch_id}")
            raise ValueError(f"No books found for exchange: {exch_id}")

        print(f"✅ Found {len(books_data)} books for exchange")

        # Convert books list to the expected format
        books_dict = {}
        for book in books_data:
            book_id = book.get('book_id')
            if book_id:
                books_dict[book_id] = {
                    'book_id': book_id,
                    'timezone': book.get('timezone', metadata.get('timezone', 'America/New_York')),
                    'base_currency': book.get('base_currency', 'USD'),
                    'initial_nav': book.get('initial_nav', 0),
                    'operation_id': book.get('operation_id', 0),
                    'engine_id': book.get('engine_id', 0),
                }

        metadata['books'] = books_dict

        # FIX: Convert datetime objects to strings if needed
        if 'last_snap' in metadata and isinstance(metadata['last_snap'], datetime):
            # Convert datetime to ISO string
            metadata['last_snap'] = metadata['last_snap'].isoformat()
            print(f"🔧 Fixed last_snap datetime to string: {metadata['last_snap']}")

        # FIX: Handle market_hours if it's missing - use database values
        if 'market_hours' not in metadata:
            print("🔧 Building market_hours from database fields")
            metadata['market_hours'] = {
                'pre_market_open': str(metadata.get('pre_market_open', '04:00')),
                'market_open': str(metadata.get('market_open', '09:30')),
                'market_close': str(metadata.get('market_close', '16:00')),
                'post_market_close': str(metadata.get('post_market_close', '20:00'))
            }

        print("🔍 DEBUG: Final metadata structure:")
        for key, value in metadata.items():
            if key == 'books':
                print(f"   {key}: dict with {len(value)} books: {list(value.keys())}")
            else:
                print(f"   {key}: {type(value).__name__} = {value}")

        return metadata

    except Exception as e:
        print(f"❌ Error loading metadata from PostgreSQL: {e}")
        print(f"❌ Full traceback: {traceback.format_exc()}")
        raise

def parse_last_snap(metadata: dict) -> tuple[datetime, str]:
    """Parse last snapshot timestamp to UTC and preserve original string"""
    try:
        print("🔄 Parsing last snap timestamp...")

        original_str = metadata.get('last_snap')
        if not original_str:
            print("❌ No 'last_snap' field found in metadata")
            raise ValueError("Missing 'last_snap' field in metadata")

        print(f"🕐 Original timestamp string: {original_str} (type: {type(original_str).__name__})")

        # Handle if it's already a datetime object
        if isinstance(original_str, datetime):
            parsed_datetime = original_str
            original_str = original_str.isoformat()
        elif isinstance(original_str, str):
            parsed_datetime = parse_iso_timestamp(original_str)
        else:
            raise ValueError(f"Unknown type for {original_str}")

        print(f"✅ Parsed timestamp: {parsed_datetime} UTC")

        return parsed_datetime, original_str

    except Exception as e:
        print(f"❌ Error parsing last snap timestamp: {e}")
        print(f"❌ Full traceback: {traceback.format_exc()}")
        raise


def parse_market_hours(metadata: dict, exchange_timezone: str, last_snap_time: datetime) -> dict:
    """Convert market hours from exchange timezone to UTC"""
    try:
        print("🔄 Parsing market hours...")
        print(f"🌍 Exchange timezone: {exchange_timezone}")
        print(f"🕐 Last snap time: {last_snap_time}")

        market_hours_data = metadata.get('market_hours', {})
        print(f"📊 Market hours data: {market_hours_data}")


        market_hours = parse_market_hours_to_utc(
            market_hours_data,
            exchange_timezone,
            last_snap_time
        )

        print(f"✅ Market hours parsed successfully")
        print(f"📊 Market hours: {market_hours}")

        return market_hours

    except Exception as e:
        print(f"❌ Error parsing market hours: {e}")
        print(f"❌ Full traceback: {traceback.format_exc()}")
        raise


def get_file_timestamp_str(original_timestamp_str: str, last_snap_time: datetime) -> str:
    """Get timestamp string for file operations"""
    try:
        if original_timestamp_str:
            try:
                dt = parse_iso_timestamp(original_timestamp_str)
                timestamp_str = dt.strftime('%Y%m%d_%H%M')
                print(f"📅 File timestamp from original: {timestamp_str}")
                return timestamp_str
            except Exception as e:
                print(f"⚠️ Could not parse original timestamp, using last_snap_time: {e}")

        timestamp_str = last_snap_time.strftime('%Y%m%d_%H%M')
        print(f"📅 File timestamp from last_snap_time: {timestamp_str}")
        return timestamp_str

    except Exception as e:
        print(f"❌ Error getting file timestamp: {e}")
        raise