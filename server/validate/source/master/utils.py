#!/usr/bin/env python3
"""
Utilities for handling master files
"""

import pandas as pd
import glob
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
import logging
from source.config import config

logger = logging.getLogger(__name__)


def get_date_from_filename(filepath: str) -> Optional[str]:
    """Extract date from master file path"""
    try:
        # Extract filename from path
        filename = Path(filepath).name
        # Look for 8-digit date pattern in filename
        import re
        date_match = re.search(r'(\d{8})', filename)
        if date_match:
            return date_match.group(1)
    except Exception as e:
        logger.warning(f"Could not extract date from {filepath}: {e}")
    return None


def find_master_files_by_date(target_date: str) -> List[str]:
    """Find all master files for a specific date"""
    date_dir = config.get_data_dir(target_date)
    if not date_dir.exists():
        logger.warning(f"Date directory does not exist: {date_dir}")
        return []

    pattern = str(date_dir / config.MASTER_FILE_PATTERN)
    files = glob.glob(pattern)
    logger.info(f"Found {len(files)} master files for date {target_date}")
    return files


def find_latest_master_file_before_date(before_date: str) -> Optional[Tuple[str, str]]:
    """Find the most recent master file before the given date

    Returns:
        Tuple of (date_string, file_path) or None if not found
    """
    try:
        target_datetime = datetime.strptime(before_date, '%Y%m%d')

        # Look for master files in date directories
        all_files = []

        # Search through potential date directories (go back up to 30 days)
        for days_back in range(1, 31):
            check_date = target_datetime - timedelta(days=days_back)
            check_date_str = check_date.strftime('%Y%m%d')

            date_dir = config.get_data_dir(check_date_str)
            if date_dir.exists():
                pattern = str(date_dir / config.MASTER_FILE_PATTERN)
                files = glob.glob(pattern)

                for file in files:
                    file_date = get_date_from_filename(file)
                    if file_date and file_date < before_date:
                        all_files.append((file_date, file))

        if not all_files:
            logger.error(f"No master files found before date {before_date}")
            return None

        # Sort by date and return the most recent
        all_files.sort(key=lambda x: x[0], reverse=True)
        latest_date, latest_file = all_files[0]
        logger.info(f"Found latest master file before {before_date}: {latest_file} (date: {latest_date})")
        return latest_date, latest_file

    except Exception as e:
        logger.error(f"Error finding latest master file before {before_date}: {e}")
        return None


def get_master_file_pair(today_date: Optional[str] = None) -> Tuple[
    Optional[Tuple[str, str]], Optional[Tuple[str, str]]]:
    """Get the pair of master files: previous and today

    Returns:
        Tuple of ((prev_date, prev_file), (today_date, today_file))
    """

    if today_date is None:
        today_date = datetime.now().strftime('%Y%m%d')

    logger.info(f"Looking for master files for today: {today_date}")

    # Find today's master file
    today_files = find_master_files_by_date(today_date)
    if not today_files:
        logger.error(f"No master file found for today: {today_date}")
        return None, None

    # Use the first master file found for today (you might want to add logic to pick the right one)
    today_file = today_files[0]
    logger.info(f"Using today's master file: {today_file}")

    # Find the most recent master file before today
    previous_result = find_latest_master_file_before_date(today_date)
    if not previous_result:
        return None, None

    previous_date, previous_file = previous_result

    return (previous_date, previous_file), (today_date, today_file)


def load_master_file(file_path: str) -> Optional[pd.DataFrame]:
    """Load master symbology file with error handling"""
    try:
        logger.info(f"Loading master file: {file_path}")
        df = pd.read_csv(file_path, sep='|', dtype=str, low_memory=False)
        df = df.fillna('')
        logger.info(f"Successfully loaded {len(df)} records from {file_path}")
        return df
    except Exception as e:
        logger.error(f"Error loading {file_path}: {e}")
        return None


def create_composite_key(df: pd.DataFrame) -> pd.DataFrame:
    """Create composite key from symbol and exchange"""
    df = df.copy()
    df['composite_key'] = df['symbol'].astype(str) + ':' + df['exchange'].astype(str)
    return df


def ensure_output_directory(date_str: str) -> Path:
    """Ensure the output directory exists for the given date"""
    output_dir = config.get_output_dir(date_str)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory ready: {output_dir}")
    return output_dir