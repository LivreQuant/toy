# source/orchestration/persistence/snapshot_loader.py
import logging
from datetime import datetime
from typing import Dict

from source.config import app_config
from source.orchestration.coordination.exchange_manager import ExchangeGroupManager
from source.utils.timezone_utils import ensure_timezone_aware

from source.orchestration.persistence.loaders.global_data_loader import GlobalDataLoader
from source.orchestration.persistence.loaders.user_data_loader import UserDataLoader
from source.orchestration.persistence.loaders.data_validator import DataValidator

from source.orchestration.coordination.metadata_handler import (
    load_metadata_from_file, load_metadata_from_postgres
)


class LastSnapLoader:
    """Main coordinator for loading all Last Snapshot data from files"""

    def __init__(self, exch_id: str):
        self.logger = logging.getLogger(self.__class__.__name__)

        self.exch_id = exch_id

        # data loaders
        self.global_loader = GlobalDataLoader()
        self.user_loader = UserDataLoader()

        self.validator = DataValidator()

    async def load_all_last_snap_data(self, date: datetime, exchange_group_manager: ExchangeGroupManager) -> Dict:
        """Load all Last Snapshot data for the given date - NOW ASYNC"""
        try:
            date = ensure_timezone_aware(date)

            self.logger.info("=" * 80)
            self.logger.info("🚀 LOADING LAST SNAPSHOT DATA")
            self.logger.info("=" * 80)
            self.logger.info(f"📅 Loading Last Snap data for {date.strftime('%Y-%m-%d')} ({date.tzinfo})")

            # Get timestamp strings
            daily_timestamp_str = date.strftime('%Y%m%d')
            intraday_timestamp_str = exchange_group_manager.get_file_timestamp_str()

            self.logger.info(f"📅 Using daily timestamp: {daily_timestamp_str}")
            self.logger.info(f"📅 Using intraday timestamp: {intraday_timestamp_str}")

            # Load metadata based on environment
            if app_config.is_production:
                self.logger.info("🔄 PRODUCTION MODE: Loading metadata from PostgreSQL")
                exchange_metadata = await load_metadata_from_postgres(self.exch_id)
            else:
                self.logger.info("🔄 DEVELOPMENT MODE: Loading metadata from JSON file")
                exchange_metadata = load_metadata_from_file()

            # Load global data - NOW ASYNC
            global_data = await self.global_loader.load_global_data(daily_timestamp_str, intraday_timestamp_str)

            # Load user data - NOW ASYNC
            user_data = await self._load_all_user_data(intraday_timestamp_str, date, exchange_group_manager)

            # Compile all data
            last_snap_data = {
                'exchange_metadata': exchange_metadata,
                'global_data': global_data,
                'user_data': user_data
            }

            # Validate and log summary
            self.validator.validate_last_snap_data(last_snap_data)
            self.validator.log_last_snap_summary(last_snap_data)

            self.logger.info("=" * 80)
            self.logger.info("✅ LAST SNAPSHOT DATA LOADING COMPLETE")
            self.logger.info("=" * 80)

            return last_snap_data

        except Exception as e:
            self.logger.error(f"❌ Error loading Last Snapshot data: {e}")
            raise

    async def _load_all_user_data(self, intraday_timestamp_str: str, date: datetime, exchange_group_manager=None) -> Dict:
        """Load data for all users - NOW ASYNC"""
        all_user_data = {}

        if exchange_group_manager:
            # Multi-user mode: get users from exchange group manager
            users = exchange_group_manager.get_all_users()
            self.logger.info(f"👥 Loading data for {len(users)} users: {users}")

            for user_id in users:
                user_data = await self.user_loader.load_user_data(user_id, intraday_timestamp_str, date)  # NOW ASYNC
                all_user_data[user_id] = user_data
        else:
            # Single-user mode: find available user directories
            available_users = None  # self.path_resolver.list_available_users()

            if not available_users:
                self.logger.warning("⚠️ No user directories found, creating default single user data")
                raise ValueError(f'No user found')
            else:
                # Load first available user for single-user mode
                user_id = available_users[0]
                self.logger.info(f"👤 Single-user mode: loading data for {user_id}")
                user_data = await self.user_loader.load_user_data(user_id, intraday_timestamp_str, date)  # NOW ASYNC
                all_user_data[user_id] = user_data

        return all_user_data

    def _get_global_data(self, daily_timestamp_str: str, intraday_timestamp_str: str) -> Dict:
        """Backward compatibility method"""
        return self.global_loader.load_global_data(daily_timestamp_str, intraday_timestamp_str)

    def _load_user_data_from_directory(self, user_id: str, intraday_timestamp_str: str,
                                       fallback_date: datetime) -> Dict:
        """Backward compatibility method"""
        return self.user_loader.load_user_data(user_id, intraday_timestamp_str, fallback_date)

    def _validate_last_snap_data(self, last_snap_data: Dict):
        """Backward compatibility method"""
        self.validator.validate_last_snap_data(last_snap_data)

    def _log_last_snap_summary(self, last_snap_data: Dict):
        """Backward compatibility method"""
        self.validator.log_last_snap_summary(last_snap_data)