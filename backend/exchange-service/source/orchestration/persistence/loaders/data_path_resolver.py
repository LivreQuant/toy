# source/orchestration/persistence/loaders/data_path_resolver.py
import os
import logging
from typing import Dict, List


class DataPathResolver:
    """Handles path resolution and file discovery for snapshot data"""

    def __init__(self, data_directory: str):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.data_directory = data_directory
        self.logger.info(f"📁 DataPathResolver using directory: {self.data_directory}")

    def get_data_directory(self) -> str:
        """Get the data directory path"""
        return self.data_directory

    def validate_data_directory(self) -> bool:
        """Validate that data directory exists"""
        if not os.path.exists(self.data_directory):
            self.logger.error(f"❌ Data directory not found: {self.data_directory}")
            return False
        return True

    def get_universe_file_path(self, daily_timestamp: str) -> str:
        """Get path to universe file (daily snapshot, JSON format)"""
        return os.path.join(self.data_directory, "universe", f"{daily_timestamp}.json")

    def get_equity_file_path(self, intraday_timestamp_str: str) -> str:
        """Get path to equity file (intraday snapshot, JSON format)"""
        return os.path.join(self.data_directory, "equity", f"{intraday_timestamp_str}.json")

    def get_fx_file_path(self, intraday_timestamp_str: str) -> str:
        """Get path to FX file (intraday snapshot, JSON format)"""
        return os.path.join(self.data_directory, "fx", f"{intraday_timestamp_str}.json")

    def get_risk_factor_file_path(self, daily_timestamp: str) -> str:
        """Get path to risk factor file (daily snapshot, JSON format)"""
        return os.path.join(self.data_directory, "risk_factors", f"{daily_timestamp}.json")

    def get_book_directory(self, book_id: str) -> str:
        """Get book directory path"""
        return os.path.join(self.data_directory, book_id)

    def get_book_file_path(self, book_id: str, data_type: str, intraday_timestamp_str: str) -> str:
        """Get path to book-specific data file (JSON format)"""
        return os.path.join(self.data_directory, book_id, data_type, f"{intraday_timestamp_str}.json")

    def get_portfolio_file_path(self, book_id: str, intraday_timestamp_str: str) -> str:
        """Get path to portfolio file (JSON format)"""
        return os.path.join(self.data_directory, book_id, "portfolio", f"{intraday_timestamp_str}.json")

    def get_account_file_path(self, book_id: str, intraday_timestamp_str: str) -> str:
        """Get path to account file (JSON format)"""
        return os.path.join(self.data_directory, book_id, "accounts", f"{intraday_timestamp_str}.json")

    def get_impact_file_path(self, book_id: str, intraday_timestamp_str: str) -> str:
        """Get path to impact file (JSON format)"""
        return os.path.join(self.data_directory, book_id, "impact", f"{intraday_timestamp_str}.json")

    def get_order_file_path(self, book_id: str, intraday_timestamp_str: str) -> str:
        """Get path to order file (JSON format)"""
        return os.path.join(self.data_directory, book_id, "orders", f"{intraday_timestamp_str}.json")

    def get_returns_file_path(self, book_id: str, intraday_timestamp_str: str) -> str:
        """Get path to returns file (JSON format)"""
        return os.path.join(self.data_directory, book_id, "returns", f"{intraday_timestamp_str}.json")

    def get_exchange_metadata_file_path(self) -> str:
        """Get path to exchange metadata file"""
        return os.path.join(self.data_directory, "exchange_group_metadata.json")

    def validate_file_exists(self, file_path: str, is_critical: bool = True) -> bool:
        """Validate that a file exists"""
        exists = os.path.exists(file_path)
        if not exists:
            if is_critical:
                self.logger.error(f"❌ Critical file missing: {file_path}")
            else:
                self.logger.warning(f"⚠️ Optional file not found: {file_path}")
        return exists

    def list_available_books(self) -> List[str]:
        """List available book directories"""
        if not os.path.exists(self.data_directory):
            return []

        book_dirs = []
        for item in os.listdir(self.data_directory):
            item_path = os.path.join(self.data_directory, item)
            if os.path.isdir(item_path) and item.startswith("BOOK_"):
                book_dirs.append(item)

        return sorted(book_dirs)

    def get_file_discovery_info(self) -> Dict:
        """Get comprehensive file discovery information for debugging"""
        info = {
            'data_directory': self.data_directory,
            'data_directory_exists': os.path.exists(self.data_directory),
            'available_books': self.list_available_books(),
            'subdirectories': []
        }

        if os.path.exists(self.data_directory):
            for item in os.listdir(self.data_directory):
                item_path = os.path.join(self.data_directory, item)
                if os.path.isdir(item_path):
                    info['subdirectories'].append(item)

        return info