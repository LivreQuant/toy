#!/usr/bin/env python3
"""
Master file loader for validation legitimacy checks
"""

import pandas as pd
import logging
from pathlib import Path
from config import config


class MasterFileLoader:
    """Loads and manages master symbology files for legitimacy checks"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.prev_master_df = pd.DataFrame()
        self.current_master_df = pd.DataFrame()
        self.load_master_files()

    def load_master_files(self):
        """Load previous and current master symbology files"""
        # Load previous day master file
        if config.PREV_MASTER_FILE:
            self.prev_master_df = self.load_csv_file(config.PREV_MASTER_FILE, "previous day master")
        else:
            self.logger.warning("Previous day master file not available - some legitimacy checks will be skipped")

        # Load current day master file
        if config.CURRENT_MASTER_FILE:
            self.current_master_df = self.load_csv_file(config.CURRENT_MASTER_FILE, "current day master")
        else:
            self.logger.warning("Current day master file not available - some legitimacy checks will be skipped")

    def load_csv_file(self, file_path: str, description: str) -> pd.DataFrame:
        """Load CSV file and return DataFrame"""
        try:
            df = pd.read_csv(file_path, dtype=str, keep_default_na=False, na_values=[])
            self.logger.info(f"Loaded {len(df)} records from {description}: {file_path}")
            return df
        except Exception as e:
            self.logger.error(f"Error loading {description} from {file_path}: {e}")
            return pd.DataFrame()

    def symbol_existed_previous_day(self, symbol: str) -> bool:
        """Check if symbol existed in previous day's master file"""
        if self.prev_master_df.empty:
            return False
        return symbol in self.prev_master_df['symbol'].values

    def symbol_exists_current_day(self, symbol: str) -> bool:
        """Check if symbol exists in current day's master file"""
        if self.current_master_df.empty:
            return False
        return symbol in self.current_master_df['symbol'].values

    def get_symbol_info_previous_day(self, symbol: str) -> pd.Series:
        """Get symbol information from previous day's master file"""
        if self.prev_master_df.empty:
            return pd.Series()

        matches = self.prev_master_df[self.prev_master_df['symbol'] == symbol]
        return matches.iloc[0] if not matches.empty else pd.Series()

    def get_symbol_info_current_day(self, symbol: str) -> pd.Series:
        """Get symbol information from current day's master file"""
        if self.current_master_df.empty:
            return pd.Series()

        matches = self.current_master_df[self.current_master_df['symbol'] == symbol]
        return matches.iloc[0] if not matches.empty else pd.Series()