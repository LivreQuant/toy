#!/usr/bin/env python3
"""
Enhanced configuration management for validation with previous day master file loading
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import glob

# Load environment variables
load_dotenv()


class ValidationConfig:
    """Configuration settings loaded from environment variables"""

    def __init__(self):
        ymd = datetime.strftime(datetime.today(), "%Y%m%d")
        prev_ymd = datetime.strftime(datetime.today() - timedelta(days=1), "%Y%m%d")

        # Master files directory
        self.MASTER_FILES_DIR = os.getenv('MASTER_FILES_DIR')

        # Corporate actions directory
        self.CORPORATE_ACTIONS_DIR = os.getenv('CORPORATE_ACTIONS_DIR')

        # Current day input files from master symbology comparison
        self.NEW_ENTRIES_FILE = \
        glob.glob(os.path.join(self.MASTER_FILES_DIR, ymd, "diff", os.getenv('NEW_ENTRIES_FILE')))[0]
        self.MISSING_ENTRIES_FILE = \
        glob.glob(os.path.join(self.MASTER_FILES_DIR, ymd, "diff", os.getenv('MISSING_ENTRIES_FILE')))[0]

        # Previous day master file for legitimacy checks
        self.PREV_MASTER_FILE = self._find_previous_master_file(prev_ymd)

        # Current day master file for legitimacy checks
        self.CURRENT_MASTER_FILE = self._find_current_master_file(ymd)

        # Output directory
        self.OUTPUT_DIR = os.path.join(self.MASTER_FILES_DIR, ymd, "diff", "validate")

        # Validate required paths
        if not self.MASTER_FILES_DIR:
            raise ValueError("MASTER_FILES_DIR not set in environment")
        if not self.CORPORATE_ACTIONS_DIR:
            raise ValueError("CORPORATE_ACTIONS_DIR not set in environment")

    def _find_previous_master_file(self, prev_ymd):
        """Find the previous day's master symbology file"""
        master_pattern = os.path.join(self.MASTER_FILES_DIR, prev_ymd, "master_symbology_*.csv")
        master_files = glob.glob(master_pattern)

        if master_files:
            # Return the most recent one if multiple exist
            return sorted(master_files)[-1]
        else:
            print(f"Warning: No previous day master file found for {prev_ymd}")
            return None

    def _find_current_master_file(self, ymd):
        """Find the current day's master symbology file"""
        master_pattern = os.path.join(self.MASTER_FILES_DIR, ymd, "master_symbology_*.csv")
        master_files = glob.glob(master_pattern)

        if master_files:
            # Return the most recent one if multiple exist
            return sorted(master_files)[-1]
        else:
            print(f"Warning: No current day master file found for {ymd}")
            return None


# Global config instance
config = ValidationConfig()