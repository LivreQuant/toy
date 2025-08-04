# source/utils/timezone_utils.py
from datetime import datetime, timezone
from typing import Optional
import logging
import zoneinfo

logger = logging.getLogger(__name__)

# Default timezone for the exchange simulator (always UTC)
DEFAULT_TIMEZONE = timezone.utc


def ensure_timezone_aware(dt: datetime, default_tz: timezone = DEFAULT_TIMEZONE) -> datetime:
    """
    Ensure a datetime object is timezone-aware.
    If it's naive, assume it's in the default timezone.
    """
    if dt is None:
        return None

    if dt.tzinfo is None:
        # Naive datetime - assume it's in default timezone
        return dt.replace(tzinfo=default_tz)

    # Already timezone-aware
    return dt


def ensure_utc(dt: datetime) -> datetime:
    """
    Ensure a datetime object is in UTC timezone.
    """
    if dt is None:
        return None

    # First make it timezone-aware if it isn't
    dt = ensure_timezone_aware(dt)

    # Convert to UTC if not already
    if dt.tzinfo != timezone.utc:
        return dt.astimezone(timezone.utc)

    return dt


def parse_iso_timestamp(timestamp_str: str, fallback_date: Optional[datetime] = None) -> datetime:
    """
    Parse ISO timestamp string and ensure it's timezone-aware in UTC.
    Handles 'Z' suffix and various ISO formats.
    """
    if not timestamp_str:
        if fallback_date:
            return ensure_utc(fallback_date)
        return datetime.now(timezone.utc)

    try:
        # Handle 'Z' suffix (UTC timezone)
        if timestamp_str.endswith('Z'):
            timestamp_str = timestamp_str[:-1] + '+00:00'

        # Parse ISO format
        dt = datetime.fromisoformat(timestamp_str)

        # Ensure timezone-aware and convert to UTC
        return ensure_utc(dt)

    except ValueError as e:
        logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}")
        if fallback_date:
            return ensure_utc(fallback_date)
        return datetime.now(timezone.utc)


def convert_market_time_to_utc(market_time_str: str, exchange_timezone_str: str) -> datetime:
    """
    Convert market time (in exchange timezone) to UTC.

    Args:
        market_time_str: Time string in HH:MM:SS format
        exchange_timezone_str: Exchange timezone (e.g., "America/New_York")

    Returns:
        datetime in UTC
    """
    try:
        exchange_tz = zoneinfo.ZoneInfo(exchange_timezone_str)

        # Parse time components
        time_parts = market_time_str.split(':')
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        second = int(time_parts[2]) if len(time_parts) > 2 else 0

        # Create a reference date (today in exchange timezone)
        now_in_exchange = datetime.now(exchange_tz)
        market_datetime = now_in_exchange.replace(
            hour=hour,
            minute=minute,
            second=second,
            microsecond=0
        )

        # Convert to UTC
        return market_datetime.astimezone(timezone.utc)

    except Exception as e:
        logger.error(f"Failed to convert market time '{market_time_str}' in timezone '{exchange_timezone_str}': {e}")
        # Fallback: assume UTC
        time_parts = market_time_str.split(':')
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        second = int(time_parts[2]) if len(time_parts) > 2 else 0

        return datetime.now(timezone.utc).replace(
            hour=hour,
            minute=minute,
            second=second,
            microsecond=0
        )


def now_utc() -> datetime:
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


def to_iso_string(dt) -> str:
    """Convert datetime to ISO string format with UTC timezone info."""
    if dt is None:
        return None

    # Handle string inputs (already ISO formatted)
    if isinstance(dt, str):
        return dt

    # Handle datetime objects
    if isinstance(dt, datetime):
        dt = ensure_utc(dt)  # Always convert to UTC
        return dt.isoformat()

    # Fallback for other types
    return str(dt)


def parse_market_hours_to_utc(market_hours: dict, exchange_timezone_str: str, reference_date: datetime) -> dict:
    """
    Parse market hours from exchange timezone to UTC.

    Args:
        market_hours: Dict with market time keys in HH:MM:SS format
        exchange_timezone_str: Exchange timezone (e.g., "America/New_York")
        reference_date: Reference date to use for the conversion

    Returns:
        Dict with UTC market hours
    """
    try:
        exchange_tz = zoneinfo.ZoneInfo(exchange_timezone_str)
        reference_date_in_exchange = reference_date.astimezone(exchange_tz)

        # Use correct keys from the actual data structure
        market_open_time = market_hours.get('market_open', '09:30:00')
        market_close_time = market_hours.get('market_close', '16:00:00')

        # Parse open time
        open_parts = market_open_time.split(':')
        open_hour = int(open_parts[0])
        open_minute = int(open_parts[1])
        open_second = int(open_parts[2]) if len(open_parts) > 2 else 0

        # Parse close time
        close_parts = market_close_time.split(':')
        close_hour = int(close_parts[0])
        close_minute = int(close_parts[1])
        close_second = int(close_parts[2]) if len(close_parts) > 2 else 0

        # Create market open/close times in exchange timezone
        market_open_exchange = reference_date_in_exchange.replace(
            hour=open_hour, minute=open_minute, second=open_second, microsecond=0
        )
        market_close_exchange = reference_date_in_exchange.replace(
            hour=close_hour, minute=close_minute, second=close_second, microsecond=0
        )

        # Convert to UTC
        market_open_utc = market_open_exchange.astimezone(timezone.utc)
        market_close_utc = market_close_exchange.astimezone(timezone.utc)

        return {
            'open_utc': market_open_utc,
            'close_utc': market_close_utc,
            'open_utc_str': market_open_utc.strftime('%H:%M:%S'),
            'close_utc_str': market_close_utc.strftime('%H:%M:%S')
        }

    except Exception as e:
        logger.error(f"Failed to parse market hours to UTC: {e}")
        # Fallback: assume already UTC
        return {
            'open_utc': reference_date.replace(hour=9, minute=30, second=0, microsecond=0),
            'close_utc': reference_date.replace(hour=16, minute=0, second=0, microsecond=0),
            'open_utc_str': '09:30:00',
            'close_utc_str': '16:00:00'
        }