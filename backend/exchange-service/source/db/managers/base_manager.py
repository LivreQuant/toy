# source/db/managers/base_manager.py
import logging
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from source.db.db_manager import DatabaseManager


class BaseTableManager:
    """Base class for all table-specific managers"""

    def __init__(self, db_manager: 'DatabaseManager'):
        self.db_manager = db_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    def _get_timestamp_str(self, timestamp_str: str) -> datetime:
        """Convert timestamp string to datetime object"""
        if len(timestamp_str) >= 13 and '_' in timestamp_str:
            # Handle YYYYMMDD_HHMM format (e.g., "20240109_1932")
            date_part = timestamp_str[:8]  # "20240109"
            time_part = timestamp_str[9:]  # "1932"
            formatted_date = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"  # "2024-01-09"
            formatted_time = f"{time_part[:2]}:{time_part[2:]}:00"  # "19:32:00"
            timestamp_string = f"{formatted_date} {formatted_time}+00:00"
            target_datetime = datetime.fromisoformat(timestamp_string)
        elif len(timestamp_str) == 8 and timestamp_str.isdigit():
            # Handle YYYYMMDD format (e.g., "20240109")
            formatted_date = f"{timestamp_str[:4]}-{timestamp_str[4:6]}-{timestamp_str[6:8]}"  # "2024-01-09"
            # Default to midnight UTC for date-only format
            timestamp_string = f"{formatted_date} 00:00:00+00:00"
            target_datetime = datetime.fromisoformat(timestamp_string)
        else:
            # Handle ISO format strings
            target_datetime = datetime.fromisoformat(timestamp_str)

        return target_datetime

    @property
    def pool(self):
        """Get the database pool from the main manager"""
        return self.db_manager.pool

    async def ensure_connection(self):
        """Ensure database connection is available"""
        if not self.pool:
            await self.db_manager.initialize()