#!/usr/bin/env python3
"""
Configuration settings
"""

import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration class"""

    def __init__(self):
        ymd = datetime.strftime(datetime.today(), "%Y%m%d")
        self.PROCESSING_YMD = ymd

        # Get CA_DATA_DIR from environment with fallback
        ca_data_dir = os.environ.get('CA_DATA_DIR')
        if ca_data_dir is None:
            raise ValueError(
                "CA_DATA_DIR environment variable is not set. "
                "Please set it to the path where corporate action data is stored."
            )
        self.CA_DATA_DIR = os.path.join(ca_data_dir, ymd, "data")

        # Get SOD_DIR from environment with fallback
        sod_dir = os.environ.get('SOD_DIR')
        if sod_dir is None:
            raise ValueError(
                "SOD_DIR environment variable is not set. "
                "Please set it to the path where start-of-day portfolio data is stored."
            )
        self.SOD_DIR = sod_dir

        # Add MANUAL_CA_DIR for manual overrides
        self.MANUAL_CA_DIR = os.path.join(ca_data_dir, "manual") if ca_data_dir else None


# Global config instance
config = Config()