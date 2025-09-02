#!/usr/bin/env python3
"""
Configuration management for validation
"""

import os
from datetime import datetime
from dotenv import load_dotenv
import glob

# Load environment variables
load_dotenv()


class ValidationConfig:
    """Configuration settings loaded from environment variables"""

    def __init__(self):
        ymd = datetime.strftime(datetime.today(), "%Y%m%d")

        # Master files directory
        self.MASTER_FILES_DIR = os.getenv('MASTER_FILES_DIR')

        # Corporate actions directory
        self.CORPORATE_ACTIONS_DIR = os.getenv('CORPORATE_ACTIONS_DIR')
        print(os.path.join(self.MASTER_FILES_DIR, ymd, "diff", os.getenv('NEW_ENTRIES_FILE')) )

        # Input files from master symbology comparison
        self.NEW_ENTRIES_FILE = glob.glob(os.path.join(self.MASTER_FILES_DIR, ymd, "diff", os.getenv('NEW_ENTRIES_FILE')))[0]
        self.MISSING_ENTRIES_FILE = glob.glob(os.path.join(self.MASTER_FILES_DIR, ymd, "diff", os.getenv('MISSING_ENTRIES_FILE')))[0]

        self.OUTPUT_DIR = os.path.join(self.MASTER_FILES_DIR, ymd, "diff", "validate")

        # Validate required paths
        if not self.MASTER_FILES_DIR:
            raise ValueError("MASTER_FILES_DIR not set in environment")
        if not self.CORPORATE_ACTIONS_DIR:
            raise ValueError("CORPORATE_ACTIONS_DIR not set in environment")


# Global config instance
config = ValidationConfig()