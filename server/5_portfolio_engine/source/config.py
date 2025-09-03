#!/usr/bin/env python3
"""
Configuration settings
"""

import os
from datetime import datetime


class Config:
    """Configuration class"""

    def __init__(self):
        ymd = datetime.strftime(datetime.today(), "%Y%m%d")

        self.PROCESSING_YMD = ymd

        self.CA_DATA_DIR = os.path.join(os.environ.get('CA_DATA_DIR'), ymd, "data")

        self.SOD_DIR = os.environ.get('SOD_DIR')


# Global config instance
config = Config()
