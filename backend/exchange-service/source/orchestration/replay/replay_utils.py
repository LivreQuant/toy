# source/orchestration/replay/replay_utils.py
"""
Utility functions for replay functionality
"""

import os
import glob
import logging
import asyncio
from typing import List

from source.config import app_config


class ReplayUtils:
    """Utility functions for replay operations"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

        # CRITICAL FIX: Only set up data directory in development mode
        if not app_config.is_production:
            current_file = os.path.abspath(__file__)
            # Navigate up from source/orchestration/replay/replay_utils.py to project root
            self.data_directory = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file)))),
                f"data")
            self.logger.info(f"🔧 DEVELOPMENT MODE: Data directory set to: {self.data_directory}")
        else:
            self.data_directory = None
            self.logger.info(f"🚫 PRODUCTION MODE: Data directory not used - PostgreSQL only")

    def get_available_bin_snaps(self) -> List[str]:
        """Get list of available bin snap files/timestamps - Environment aware"""

        # CHECK FOR PRODUCTION MODE FIRST
        if app_config.is_production:
            self.logger.info("🔄 PRODUCTION MODE: Getting available bin snaps from PostgreSQL")
            return self._get_available_bin_snaps_from_postgres()
        else:
            self.logger.info("🔄 DEVELOPMENT MODE: Getting available bin snaps from files")
            return self._get_available_bin_snaps_from_files()

    def _get_available_bin_snaps_from_files(self) -> List[str]:
        """Get list of available bin snap files in data directory (development)"""
        if not self.data_directory or not os.path.exists(self.data_directory):
            self.logger.warning("⚠️ Data directory not available for file-based bin snap discovery")
            return []

        try:
            equity_pattern = os.path.join(self.data_directory, "equity", "????????_????.csv")
            fx_pattern = os.path.join(self.data_directory, "fx", "????????_????.csv")

            equity_files = glob.glob(equity_pattern)
            fx_files = glob.glob(fx_pattern)

            # Extract timestamps from filenames
            timestamps = set()
            for file_path in equity_files + fx_files:
                filename = os.path.basename(file_path)
                timestamp = filename.replace('.csv', '')
                timestamps.add(timestamp)

            sorted_timestamps = sorted(list(timestamps))
            self.logger.info(f"📁 Found {len(sorted_timestamps)} bin snap timestamps")
            return sorted_timestamps

        except Exception as e:
            self.logger.error(f"❌ Error discovering bin snap files: {e}")
            return []

    def _get_available_bin_snaps_from_postgres(self) -> List[str]:
        """Get list of available bin snap timestamps from PostgreSQL (production)"""
        try:
            from source.db.db_manager import db_manager

            async def get_timestamps_async():
                await db_manager.initialize()
                return await db_manager.get_available_bin_snap_timestamps()

            # Use asyncio to run the async function
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, create a new event loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, get_timestamps_async())
                    timestamps = future.result()
            else:
                timestamps = asyncio.run(get_timestamps_async())

            self.logger.info(f"💾 Found {len(timestamps)} bin snap timestamps in PostgreSQL")
            return timestamps

        except Exception as e:
            self.logger.error(f"❌ Error getting bin snap timestamps from PostgreSQL: {e}")
            return []

    def get_replay_data_summary(self) -> dict:
        """Get summary of available replay data"""
        if app_config.is_production:
            return self._get_replay_data_summary_from_postgres()
        else:
            return self._get_replay_data_summary_from_files()

    def _get_replay_data_summary_from_files(self) -> dict:
        """Get replay data summary from files (development)"""
        if not self.data_directory or not os.path.exists(self.data_directory):
            return {
                'total_timestamps': 0,
                'date_range': None,
                'data_types': [],
                'status': 'no_data_directory'
            }

        try:
            timestamps = self.get_available_bin_snaps()

            summary = {
                'total_timestamps': len(timestamps),
                'date_range': {
                    'start': timestamps[0] if timestamps else None,
                    'end': timestamps[-1] if timestamps else None
                },
                'data_types': [],
                'status': 'ready'
            }

            # Check for different data types
            if os.path.exists(os.path.join(self.data_directory, "equity")):
                summary['data_types'].append('equity')
            if os.path.exists(os.path.join(self.data_directory, "fx")):
                summary['data_types'].append('fx')
            if os.path.exists(os.path.join(self.data_directory, "universe")):
                summary['data_types'].append('universe')

            return summary

        except Exception as e:
            self.logger.error(f"❌ Error getting replay data summary from files: {e}")
            return {
                'total_timestamps': 0,
                'date_range': None,
                'data_types': [],
                'status': 'error',
                'error': str(e)
            }

    def _get_replay_data_summary_from_postgres(self) -> dict:
        """Get replay data summary from PostgreSQL (production)"""
        try:
            from source.db.db_manager import db_manager

            async def get_summary_async():
                await db_manager.initialize()
                return await db_manager.get_replay_data_summary()

            # Use asyncio to run the async function
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, create a new event loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, get_summary_async())
                    summary = future.result()
            else:
                summary = asyncio.run(get_summary_async())

            return summary

        except Exception as e:
            self.logger.error(f"❌ Error getting replay data summary from PostgreSQL: {e}")
            return {
                'total_timestamps': 0,
                'date_range': None,
                'data_types': [],
                'status': 'error',
                'error': str(e)
            }

    def validate_replay_data(self, start_timestamp: str, end_timestamp: str) -> dict:
        """Validate that replay data is available for the given range"""
        if app_config.is_production:
            return self._validate_replay_data_postgres(start_timestamp, end_timestamp)
        else:
            return self._validate_replay_data_files(start_timestamp, end_timestamp)

    def _validate_replay_data_files(self, start_timestamp: str, end_timestamp: str) -> dict:
        """Validate replay data from files (development)"""
        available_timestamps = self.get_available_bin_snaps()

        # Filter timestamps within range
        filtered_timestamps = [
            ts for ts in available_timestamps
            if start_timestamp <= ts <= end_timestamp
        ]

        return {
            'valid': len(filtered_timestamps) > 0,
            'available_timestamps': len(filtered_timestamps),
            'total_in_range': len(filtered_timestamps),
            'missing_timestamps': [],
            'status': 'valid' if filtered_timestamps else 'no_data_in_range'
        }

    def _validate_replay_data_postgres(self, start_timestamp: str, end_timestamp: str) -> dict:
        """Validate replay data from PostgreSQL (production)"""
        try:
            from source.db.db_manager import db_manager

            async def validate_async():
                await db_manager.initialize()
                return await db_manager.validate_replay_data_range(start_timestamp, end_timestamp)

            # Use asyncio to run the async function
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, create a new event loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, validate_async())
                    validation_result = future.result()
            else:
                validation_result = asyncio.run(validate_async())

            return validation_result

        except Exception as e:
            self.logger.error(f"❌ Error validating replay data from PostgreSQL: {e}")
            return {
                'valid': False,
                'available_timestamps': 0,
                'total_in_range': 0,
                'missing_timestamps': [],
                'status': 'error',
                'error': str(e)
            }