# source/orchestration/coordination/metadata_handler.py
import asyncio
import json
import os
import traceback
import logging
from datetime import datetime

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


async def load_metadata_from_postgres(group_id: str) -> dict:
    """Load metadata from PostgreSQL (production) - async version"""
    try:
        print(f"🔄 Loading metadata from PostgreSQL for group_id: {group_id}")

        # Import here to avoid circular imports
        from source.db.db_manager import db_manager

        print("🔄 Initializing database connection...")
        await db_manager.initialize()
        print("✅ Database connection initialized")

        print(f"🔍 Loading metadata for group_id: {group_id}")
        metadata = await db_manager.load_exchange_metadata(group_id)

        # Validate metadata
        if not metadata:
            print(f"❌ No metadata returned from database for group_id: {group_id}")
            raise ValueError(f"No metadata found for group_id: {group_id}")

        print(f"✅ PostgreSQL metadata loaded for group: {metadata.get('group_id', 'UNKNOWN')}")

        # DEBUG: Print all metadata fields and their types
        print("🔍 DEBUG: Metadata fields and types:")
        for key, value in metadata.items():
            print(f"   {key}: {type(value).__name__} = {value}")

        # Get the exch_id from metadata
        exch_id = metadata.get('exch_id')
        if not exch_id:
            raise ValueError("No exch_id found in metadata")

        print(f"🔍 Found exch_id: {exch_id}")

        # Load users for this exchange
        print(f"🔄 Loading users for exch_id: {exch_id}")
        users_data = await db_manager.load_users_for_exchange(exch_id)

        if not users_data:
            print(f"❌ No users found for exch_id: {exch_id}")
            raise ValueError(f"No users found for exchange: {exch_id}")

        print(f"✅ Found {len(users_data)} users for exchange")

        # Convert users list to the expected format
        users_dict = {}
        for user in users_data:
            user_id = user.get('user_id')
            if user_id:
                users_dict[user_id] = {
                    'user_id': user_id,
                    'base_currency': user.get('base_currency', 'USD'),
                    'timezone': user.get('timezone', metadata.get('timezone', 'America/New_York')),
                    'updated_time': user.get('updated_time')
                }

        metadata['users'] = users_dict

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
            if key == 'users':
                print(f"   {key}: dict with {len(value)} users: {list(value.keys())}")
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

        from source.utils.timezone_utils import parse_iso_timestamp

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

        from source.utils.timezone_utils import parse_market_hours_to_utc

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
                from source.utils.timezone_utils import parse_iso_timestamp
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