#!/usr/bin/env python3
"""
Configuration management for master file comparison
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from typing import Set

# Load environment variables
load_dotenv()


class Config:
    """Configuration settings loaded from environment variables"""

    # Master file settings
    MASTER_FILE_DIR = Path(os.getenv('MASTER_FILE_DIR', '/media/samaral/pro/alphastamp/master'))
    MASTER_FILE_PATTERN = os.getenv('MASTER_FILE_PATTERN', '*_MASTER.csv')

    # Columns to ignore in comparison
    _ignore_columns_str = os.getenv('IGNORE_COLUMNS',
                                    'composite_key,change_type,change_timestamp,previous_date,current_date,market_capital,scalemarketcap,shares_outstanding,share_class_shares_outstanding,weighted_shares_outstanding,earnings_announcement')
    IGNORE_COLUMNS = set(col.strip() for col in _ignore_columns_str.split(',') if col.strip())

    # Columns that should be treated as numeric
    _numeric_columns_str = os.getenv('NUMERIC_COLUMNS',
                                     'market_capital,scalemarketcap,shares_outstanding,share_class_shares_outstanding,weighted_shares_outstanding,lot,margin_requirement_short,margin_requirement_long,maintenance_margin_requirement,sic_code')
    NUMERIC_COLUMNS = set(col.strip() for col in _numeric_columns_str.split(',') if col.strip())

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    def get_output_dir(self, date_str: str) -> Path:
        """Get the output directory for a specific date"""
        return self.MASTER_FILE_DIR / date_str / "diff"

    def get_data_dir(self, date_str: str) -> Path:
        """Get the data directory for a specific date"""
        return self.MASTER_FILE_DIR / date_str / "data"

    @classmethod
    def validate_config(cls):
        """Validate that required configuration is present"""
        if not cls.MASTER_FILE_DIR.exists():
            raise FileNotFoundError(f"Master file directory does not exist: {cls.MASTER_FILE_DIR}")
        return True

    def print_config(self):
        """Print current configuration for debugging"""
        return {
            'MASTER_FILE_DIR': str(self.MASTER_FILE_DIR),
            'MASTER_FILE_PATTERN': self.MASTER_FILE_PATTERN,
            'IGNORE_COLUMNS': sorted(list(self.IGNORE_COLUMNS)),
            'NUMERIC_COLUMNS': sorted(list(self.NUMERIC_COLUMNS)),
            'LOG_LEVEL': self.LOG_LEVEL
        }


# Global config instance
config = Config()