#!/usr/bin/env python3
"""
Master file comparison engine with proper numeric comparison and configurable ignore columns
"""

import pandas as pd
from typing import Dict, Tuple, Any
import logging
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from source.config import config
from source.master.utils import ensure_output_directory

logger = logging.getLogger(__name__)


class MasterFileComparator:
    """Compare two master files and identify all differences with proper numeric handling"""

    def __init__(self, previous_df: pd.DataFrame, current_df: pd.DataFrame,
                 previous_date: str, current_date: str):
        self.previous_df = previous_df.copy()
        self.current_df = current_df.copy()
        self.previous_date = previous_date
        self.current_date = current_date

        # Add composite keys
        self.previous_df['composite_key'] = (
                self.previous_df['symbol'].astype(str) + ':' +
                self.previous_df['exchange'].astype(str)
        )
        self.current_df['composite_key'] = (
                self.current_df['symbol'].astype(str) + ':' +
                self.current_df['exchange'].astype(str)
        )

        # Create sets for comparison
        self.previous_keys = set(self.previous_df['composite_key'])
        self.current_keys = set(self.current_df['composite_key'])

        # Ensure output directory exists
        self.output_dir = ensure_output_directory(current_date)

        # Log configuration being used
        logger.info(f"Using ignore columns: {sorted(list(config.IGNORE_COLUMNS))}")
        logger.info(f"Using numeric columns: {sorted(list(config.NUMERIC_COLUMNS))}")
        logger.info(f"Previous file ({previous_date}): {len(self.previous_df)} records")
        logger.info(f"Current file ({current_date}): {len(self.current_df)} records")
        logger.info(f"Output directory: {self.output_dir}")

    def normalize_numeric_value(self, value: Any, column_name: str) -> str:
        """Normalize numeric values for comparison"""
        if column_name not in config.NUMERIC_COLUMNS:
            return str(value) if pd.notna(value) else ''

        try:
            # Handle empty/null values
            if pd.isna(value) or value == '' or value == 'nan':
                return '0'

            # Convert to float first
            float_val = float(str(value).replace(',', ''))

            # If it's a whole number, return as integer string
            if float_val.is_integer():
                return str(int(float_val))
            else:
                # Round to avoid floating point precision issues
                return f"{float_val:.10g}"  # Use general format to avoid unnecessary decimals

        except (ValueError, TypeError) as e:
            logger.debug(f"Could not convert '{value}' to numeric for column '{column_name}': {e}")
            return str(value) if pd.notna(value) else ''

    def values_are_equal(self, val1: Any, val2: Any, column_name: str) -> bool:
        """Compare two values, handling numeric columns specially"""
        if column_name in config.NUMERIC_COLUMNS:
            norm_val1 = self.normalize_numeric_value(val1, column_name)
            norm_val2 = self.normalize_numeric_value(val2, column_name)
            return norm_val1 == norm_val2
        else:
            # String comparison
            str_val1 = str(val1) if pd.notna(val1) else ''
            str_val2 = str(val2) if pd.notna(val2) else ''
            return str_val1 == str_val2

    def get_display_value(self, value: Any, column_name: str) -> str:
        """Get the display value for output"""
        if column_name in config.NUMERIC_COLUMNS:
            return self.normalize_numeric_value(value, column_name)
        else:
            return str(value) if pd.notna(value) else ''

    def find_new_entries(self) -> pd.DataFrame:
        """Find symbol/exchange pairs that are new in current file"""
        new_keys = self.current_keys - self.previous_keys
        new_entries = self.current_df[self.current_df['composite_key'].isin(new_keys)].copy()
        new_entries['change_type'] = 'NEW_ENTRY'
        new_entries['change_timestamp'] = datetime.now().isoformat()
        new_entries['previous_date'] = self.previous_date
        new_entries['current_date'] = self.current_date

        logger.info(f"Found {len(new_entries)} new entries")
        return new_entries

    def find_missing_entries(self) -> pd.DataFrame:
        """Find symbol/exchange pairs that disappeared from current file"""
        missing_keys = self.previous_keys - self.current_keys
        missing_entries = self.previous_df[self.previous_df['composite_key'].isin(missing_keys)].copy()
        missing_entries['change_type'] = 'MISSING_ENTRY'
        missing_entries['change_timestamp'] = datetime.now().isoformat()
        missing_entries['previous_date'] = self.previous_date
        missing_entries['current_date'] = self.current_date

        logger.info(f"Found {len(missing_entries)} missing entries")
        return missing_entries

    def find_data_changes_detailed(self) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
        """Find changes in existing symbol/exchange pairs and organize by column"""
        common_keys = self.previous_keys & self.current_keys

        if not common_keys:
            logger.info("No common keys found for comparison")
            return pd.DataFrame(), {}

        # Create indexed DataFrames for efficient comparison
        prev_indexed = self.previous_df.set_index('composite_key')
        curr_indexed = self.current_df.set_index('composite_key')

        # Track changes by column
        column_changes = defaultdict(list)
        summary_changes = []

        logger.info(f"Comparing {len(common_keys)} common records for data changes...")
        logger.info(f"Ignoring columns: {sorted(list(config.IGNORE_COLUMNS))}")

        ignored_due_to_numeric = 0
        total_comparisons = 0

        for i, key in enumerate(common_keys):
            if i % 5000 == 0:  # Progress indicator
                logger.info(f"Processed {i}/{len(common_keys)} records")

            try:
                prev_row = prev_indexed.loc[key]
                curr_row = curr_indexed.loc[key]

                symbol, exchange = key.split(':', 1)

                # Find differences
                row_changes = {}
                for col in prev_row.index:
                    if col in config.IGNORE_COLUMNS:
                        continue

                    if col in curr_row.index:
                        total_comparisons += 1
                        prev_val = prev_row[col]
                        curr_val = curr_row[col]

                        if not self.values_are_equal(prev_val, curr_val, col):
                            # Get display values
                            prev_display = self.get_display_value(prev_val, col)
                            curr_display = self.get_display_value(curr_val, col)

                            row_changes[col] = {
                                'previous_value': prev_display,
                                'current_value': curr_display,
                                'original_previous': str(prev_val) if pd.notna(prev_val) else '',
                                'original_current': str(curr_val) if pd.notna(curr_val) else ''
                            }

                            # Add to column-specific tracking
                            column_changes[col].append({
                                'symbol': symbol,
                                'exchange': exchange,
                                'composite_key': key,
                                'previous_value': prev_display,
                                'current_value': curr_display,
                                'original_previous_value': str(prev_val) if pd.notna(prev_val) else '',
                                'original_current_value': str(curr_val) if pd.notna(curr_val) else '',
                                'is_numeric_column': col in config.NUMERIC_COLUMNS,
                                'previous_date': self.previous_date,
                                'current_date': self.current_date,
                                'change_timestamp': datetime.now().isoformat()
                            })
                        else:
                            # Track numeric normalizations for debugging
                            if col in config.NUMERIC_COLUMNS and str(prev_val) != str(curr_val):
                                ignored_due_to_numeric += 1

                if row_changes:
                    # Create a summary record for this symbol
                    change_record = {
                        'symbol': symbol,
                        'exchange': exchange,
                        'composite_key': key,
                        'change_type': 'DATA_CHANGE',
                        'change_timestamp': datetime.now().isoformat(),
                        'previous_date': self.previous_date,
                        'current_date': self.current_date,
                        'changed_fields': ', '.join(sorted(row_changes.keys())),
                        'change_count': len(row_changes)
                    }

                    # Add some key current values for context
                    for field in ['name', 'status', 'type', 'currency']:
                        if field in curr_row.index:
                            change_record[field] = str(curr_row[field])

                    summary_changes.append(change_record)

            except Exception as e:
                logger.warning(f"Error comparing key {key}: {e}")
                continue

        # Convert to DataFrames
        summary_df = pd.DataFrame(summary_changes) if summary_changes else pd.DataFrame()
        column_dfs = {col: pd.DataFrame(changes) for col, changes in column_changes.items()}

        logger.info(f"Numeric normalizations prevented {ignored_due_to_numeric} false positives")

        if summary_changes:
            logger.info(f"Found {len(summary_df)} records with data changes across {len(column_dfs)} columns")

            # Log top changed columns
            column_counts = [(col, len(df)) for col, df in column_dfs.items()]
            column_counts.sort(key=lambda x: x[1], reverse=True)
            logger.info("Top 5 changed columns:")
            for col, count in column_counts[:5]:
                logger.info(f"  {col}: {count} changes")
        else:
            logger.info("No data changes found")

        return summary_df, column_dfs

    def create_column_changes_summary(self, column_dfs: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Create a summary of changes by column"""
        summary_data = []

        for column_name, changes_df in column_dfs.items():
            if changes_df.empty:
                continue

            # Analyze the types of changes in this column
            unique_changes = len(changes_df)
            unique_symbols = changes_df['symbol'].nunique()
            is_numeric = changes_df.iloc[0]['is_numeric_column'] if 'is_numeric_column' in changes_df.columns else False

            # Get unique value transitions to understand the nature of changes
            transitions = changes_df[['previous_value', 'current_value']].drop_duplicates()
            unique_transitions = len(transitions)

            # Sample some changes for preview (showing both original and normalized for numeric)
            sample_size = min(3, len(changes_df))
            sample_data = []

            for _, row in changes_df.head(sample_size).iterrows():
                sample_info = {
                    'symbol': row['symbol'],
                    'exchange': row['exchange'],
                    'prev': row['previous_value'],
                    'curr': row['current_value']
                }

                # Add original values for numeric columns if different
                if is_numeric and 'original_previous_value' in row:
                    if row['original_previous_value'] != row['previous_value'] or row['original_current_value'] != row[
                        'current_value']:
                        sample_info['orig_prev'] = row['original_previous_value']
                        sample_info['orig_curr'] = row['original_current_value']

                sample_data.append(sample_info)

            summary_data.append({
                'column_name': column_name,
                'is_numeric': is_numeric,
                'total_changes': unique_changes,
                'affected_symbols': unique_symbols,
                'unique_transitions': unique_transitions,
                'sample_changes': str(sample_data),
                'output_file': f"comparison_{self.previous_date}_to_{self.current_date}_column_{column_name}_changes.csv"
            })

        return pd.DataFrame(summary_data).sort_values('total_changes', ascending=False)

    def generate_comparison_summary(self) -> Dict[str, Any]:
        """Generate a summary of all changes"""
        new_entries = self.find_new_entries()
        missing_entries = self.find_missing_entries()
        data_changes_summary, column_changes = self.find_data_changes_detailed()

        # Create column summary
        column_summary = self.create_column_changes_summary(column_changes)

        summary = {
            'comparison_timestamp': datetime.now().isoformat(),
            'previous_date': self.previous_date,
            'current_date': self.current_date,
            'previous_file_records': len(self.previous_df),
            'current_file_records': len(self.current_df),
            'net_change': len(self.current_df) - len(self.previous_df),
            'new_entries_count': len(new_entries),
            'missing_entries_count': len(missing_entries),
            'data_changes_count': len(data_changes_summary),
            'columns_changed_count': len(column_changes),
            'total_changes': len(new_entries) + len(missing_entries) + len(data_changes_summary),
            'common_records': len(self.previous_keys & self.current_keys),
            'output_directory': str(self.output_dir),
            'ignored_columns': sorted(list(config.IGNORE_COLUMNS)),
            'numeric_columns': sorted(list(config.NUMERIC_COLUMNS))
        }

        return summary, new_entries, missing_entries, data_changes_summary, column_changes, column_summary

    def save_results(self, output_prefix: str = None) -> Dict[str, str]:
        """Save all comparison results to files"""
        if output_prefix is None:
            output_prefix = f"comparison_{self.previous_date}_to_{self.current_date}"

        summary, new_entries, missing_entries, data_changes_summary, column_changes, column_summary = self.generate_comparison_summary()

        output_files = {}

        # Save new entries
        if not new_entries.empty:
            new_file = self.output_dir / f"{output_prefix}_new_entries.csv"
            new_entries.to_csv(new_file, index=False)
            output_files['new_entries'] = str(new_file)
            logger.info(f"Saved {len(new_entries)} new entries to {new_file}")

        # Save missing entries
        if not missing_entries.empty:
            missing_file = self.output_dir / f"{output_prefix}_missing_entries.csv"
            missing_entries.to_csv(missing_file, index=False)
            output_files['missing_entries'] = str(missing_file)
            logger.info(f"Saved {len(missing_entries)} missing entries to {missing_file}")

        # Save data changes summary
        if not data_changes_summary.empty:
            changes_summary_file = self.output_dir / f"{output_prefix}_data_changes_summary.csv"
            data_changes_summary.to_csv(changes_summary_file, index=False)
            output_files['data_changes_summary'] = str(changes_summary_file)
            logger.info(f"Saved {len(data_changes_summary)} data change summaries to {changes_summary_file}")

        # Save column-specific changes
        column_files_created = 0
        for column_name, changes_df in column_changes.items():
            if changes_df.empty:
                continue

            # Clean column name for filename
            clean_column_name = column_name.replace('/', '_').replace(' ', '_').replace('|', '_')
            column_file = self.output_dir / f"{output_prefix}_column_{clean_column_name}_changes.csv"
            changes_df.to_csv(column_file, index=False)
            output_files[f'column_{clean_column_name}'] = str(column_file)
            column_files_created += 1

        logger.info(f"Saved {column_files_created} column-specific change files")

        # Save column summary
        if not column_summary.empty:
            column_summary_file = self.output_dir / f"{output_prefix}_columns_summary.csv"
            column_summary.to_csv(column_summary_file, index=False)
            output_files['columns_summary'] = str(column_summary_file)
            logger.info(f"Saved column summary to {column_summary_file}")

        # Save comprehensive summary with configuration info
        summary_file = self.output_dir / f"{output_prefix}_summary.txt"
        with open(summary_file, 'w') as f:
            f.write("MASTER FILE COMPARISON SUMMARY\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"Comparison: {self.previous_date} -> {self.current_date}\n")
            f.write(f"Output Directory: {self.output_dir}\n\n")

            f.write("CONFIGURATION:\n")
            f.write("-" * 20 + "\n")
            f.write(
                f"Ignored Columns ({len(config.IGNORE_COLUMNS)}): {', '.join(sorted(list(config.IGNORE_COLUMNS)))}\n")
            f.write(
                f"Numeric Columns ({len(config.NUMERIC_COLUMNS)}): {', '.join(sorted(list(config.NUMERIC_COLUMNS)))}\n\n")

            f.write("OVERVIEW:\n")
            f.write("-" * 20 + "\n")
            for key, value in summary.items():
                if key not in ['ignored_columns', 'numeric_columns']:  # Already shown above
                    f.write(f"{key}: {value}\n")
            f.write("\n")

            # Add detailed breakdown
            f.write("DETAILED BREAKDOWN:\n")
            f.write("-" * 30 + "\n")
            if summary['new_entries_count'] > 0:
                f.write(f"📈 NEW ENTRIES ({summary['new_entries_count']})\n")
                f.write("   - Symbol/exchange pairs that appeared in current file\n")
                f.write(f"   - File: {Path(output_files.get('new_entries', 'N/A')).name}\n\n")

            if summary['missing_entries_count'] > 0:
                f.write(f"📉 MISSING ENTRIES ({summary['missing_entries_count']})\n")
                f.write("   - Symbol/exchange pairs that disappeared from current file\n")
                f.write(f"   - File: {Path(output_files.get('missing_entries', 'N/A')).name}\n\n")

            if summary['data_changes_count'] > 0:
                f.write(
                    f"🔄 DATA CHANGES ({summary['data_changes_count']} symbols across {summary['columns_changed_count']} columns)\n")
                f.write("   - Existing symbol/exchange pairs with modified data\n")
                f.write("   - Numeric values normalized for comparison (30.0 = 30)\n")
                f.write(f"   - Summary: {Path(output_files.get('data_changes_summary', 'N/A')).name}\n")
                f.write(f"   - Column Summary: {Path(output_files.get('columns_summary', 'N/A')).name}\n")

                # List top changed columns
                if not column_summary.empty:
                    f.write("   - Top Changed Columns:\n")
                    for _, row in column_summary.head(10).iterrows():
                        numeric_flag = " (numeric)" if row.get('is_numeric', False) else ""
                        f.write(
                            f"     • {row['column_name']}{numeric_flag}: {row['total_changes']} changes in {row['affected_symbols']} symbols\n")
                f.write("\n")

            f.write(f"📊 TOTAL CHANGES: {summary['total_changes']}\n")
            f.write("\nFILES GENERATED:\n")
            f.write("-" * 20 + "\n")
            for file_type, file_path in output_files.items():
                f.write(f"{file_type}: {Path(file_path).name}\n")

        output_files['summary'] = str(summary_file)
        logger.info(f"Saved comprehensive summary to {summary_file}")

        return output_files, summary