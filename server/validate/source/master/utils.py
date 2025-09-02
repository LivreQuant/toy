#!/usr/bin/env python3
"""
Utilities for handling master files with USE_PREV functionality
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


def ensure_primary_diff_directory(date_str: str) -> Path:
    """Ensure the primary diff directory exists for the given date"""
    primary_dir = config.get_primary_diff_dir(date_str)
    primary_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Primary diff directory ready: {primary_dir}")
    return primary_dir


def ensure_secondary_diff_directory(date_str: str) -> Path:
    """Ensure the secondary diff directory exists for the given date"""
    secondary_dir = config.get_secondary_diff_dir(date_str)
    secondary_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Secondary diff directory ready: {secondary_dir}")
    return secondary_dir


def create_updated_master_with_prev_data(current_df: pd.DataFrame, previous_df: pd.DataFrame,
                                         current_date: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Create updated master file using previous day's data for USE_PREV columns when current data is empty.

    Returns:
        Tuple of (updated_current_df, use_prev_changes_df)
    """
    if config.USE_PREV_COLUMNS is None or len(config.USE_PREV_COLUMNS) == 0:
        logger.info("No USE_PREV columns configured, returning original data")
        return current_df.copy(), pd.DataFrame()

    logger.info(f"Processing USE_PREV columns: {sorted(list(config.USE_PREV_COLUMNS))}")

    # Create composite keys if they don't exist
    current_with_key = current_df.copy()
    previous_with_key = previous_df.copy()

    if 'composite_key' not in current_with_key.columns:
        current_with_key['composite_key'] = (
                current_with_key['symbol'].astype(str) + ':' +
                current_with_key['exchange'].astype(str)
        )

    if 'composite_key' not in previous_with_key.columns:
        previous_with_key['composite_key'] = (
                previous_with_key['symbol'].astype(str) + ':' +
                previous_with_key['exchange'].astype(str)
        )

    # Set composite_key as index for efficient lookups
    current_indexed = current_with_key.set_index('composite_key')
    previous_indexed = previous_with_key.set_index('composite_key')

    # Find common keys
    common_keys = set(current_indexed.index) & set(previous_indexed.index)
    logger.info(f"Found {len(common_keys)} common symbols for USE_PREV processing")

    use_prev_changes = []
    updates_made = 0

    # Process each common symbol
    for composite_key in common_keys:
        try:
            current_row = current_indexed.loc[composite_key]
            previous_row = previous_indexed.loc[composite_key]

            symbol, exchange = composite_key.split(':', 1)
            row_updated = False
            fields_updated = []

            # Check each USE_PREV column
            for col in config.USE_PREV_COLUMNS:
                if col in current_indexed.columns and col in previous_indexed.columns:
                    current_val = str(current_row[col]).strip() if pd.notna(current_row[col]) else ''
                    previous_val = str(previous_row[col]).strip() if pd.notna(previous_row[col]) else ''

                    # If current value is empty but previous value exists
                    if (current_val == '' or current_val == 'nan') and previous_val != '' and previous_val != 'nan':
                        # Update current data with previous value
                        current_indexed.loc[composite_key, col] = previous_val
                        row_updated = True
                        fields_updated.append(col)

                        # Record the change
                        use_prev_changes.append({
                            'symbol': symbol,
                            'exchange': exchange,
                            'composite_key': composite_key,
                            'column': col,
                            'current_value': current_val,
                            'previous_value': previous_val,
                            'updated_value': previous_val,
                            'change_type': 'USE_PREV_BACKFILL',
                            'change_timestamp': datetime.now().isoformat(),
                            'current_date': current_date
                        })

            if row_updated:
                updates_made += 1
                logger.debug(f"Updated {composite_key}: {', '.join(fields_updated)}")

        except Exception as e:
            logger.warning(f"Error processing USE_PREV for {composite_key}: {e}")
            continue

    logger.info(
        f"USE_PREV processing complete: Updated {updates_made} symbols across {len(use_prev_changes)} field changes")

    # Convert back to DataFrame with reset index
    updated_current_df = current_indexed.reset_index()
    use_prev_changes_df = pd.DataFrame(use_prev_changes)

    return updated_current_df, use_prev_changes_df


def save_updated_master_file(updated_df: pd.DataFrame, current_date: str,
                             original_filename: str) -> str:
    """
    Save the updated master file with USE_PREV backfilled data.

    Returns:
        Path to the saved updated master file
    """
    # Create the updated filename
    data_dir = config.get_data_dir(current_date)
    original_path = Path(original_filename)

    # Create new filename with _UPDATED suffix
    updated_filename = f"{original_path.stem}_UPDATED{original_path.suffix}"
    updated_file_path = data_dir / updated_filename

    # Remove composite_key if it was added during processing
    output_df = updated_df.copy()
    if 'composite_key' in output_df.columns:
        output_df = output_df.drop('composite_key', axis=1)

    # Save the updated file
    output_df.to_csv(updated_file_path, sep='|', index=False)
    logger.info(f"Saved updated master file: {updated_file_path}")

    return str(updated_file_path)