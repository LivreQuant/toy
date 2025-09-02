#!/usr/bin/env python3
"""
Master file comparison engine with USE_PREV functionality and primary/secondary diff categorization
"""

import pandas as pd
from typing import Dict, Tuple, Any
import logging
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from source.config import config
from source.master.utils import (
    ensure_output_directory,
    ensure_primary_diff_directory,
    ensure_secondary_diff_directory,
    create_updated_master_with_prev_data,
    save_updated_master_file
)

logger = logging.getLogger(__name__)


class MasterFileComparator:
    """Compare two master files and identify all differences with USE_PREV functionality"""

    def __init__(self, previous_df: pd.DataFrame, current_df: pd.DataFrame,
                 previous_date: str, current_date: str, original_current_filename: str = None):
        self.original_previous_df = previous_df.copy()
        self.original_current_df = current_df.copy()
        self.previous_date = previous_date
        self.current_date = current_date
        self.original_current_filename = original_current_filename

        # Process USE_PREV columns and create updated master
        logger.info("Processing USE_PREV columns...")
        self.updated_current_df, self.use_prev_changes_df = create_updated_master_with_prev_data(
            current_df, previous_df, current_date
        )

        # Save updated master file if changes were made
        self.updated_master_file = None
        if not self.use_prev_changes_df.empty and original_current_filename:
            self.updated_master_file = save_updated_master_file(
                self.updated_current_df, current_date, original_current_filename
            )
            logger.info(f"Created updated master file: {self.updated_master_file}")

        # Use updated dataframes for comparison
        self.previous_df = self.original_previous_df.copy()
        self.current_df = self.updated_current_df.copy()

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

        # Ensure all output directories exist
        self.output_dir = ensure_output_directory(current_date)
        self.primary_diff_dir = ensure_primary_diff_directory(current_date)
        self.secondary_diff_dir = ensure_secondary_diff_directory(current_date)

        # Log configuration being used
        logger.info(f"Using ignore columns: {sorted(list(config.IGNORE_COLUMNS))}")
        logger.info(f"Using numeric columns: {sorted(list(config.NUMERIC_COLUMNS))}")
        logger.info(f"Using USE_PREV columns: {sorted(list(config.USE_PREV_COLUMNS))}")
        logger.info(f"Previous file ({previous_date}): {len(self.previous_df)} records")
        logger.info(f"Current file ({current_date}): {len(self.current_df)} records")
        logger.info(f"USE_PREV changes: {len(self.use_prev_changes_df)} field updates")
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"Primary diff directory: {self.primary_diff_dir}")
        logger.info(f"Secondary diff directory: {self.secondary_diff_dir}")

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

    def is_use_prev_related_change(self, column_name: str, prev_val: Any, curr_val: Any) -> bool:
        """
        Determine if a change is related to USE_PREV functionality.
        This happens when:
        1. The column is in USE_PREV_COLUMNS, AND
        2. Previous value was empty and current value is now filled (due to backfill)
        """
        if column_name not in config.USE_PREV_COLUMNS:
            return False

        prev_str = str(prev_val).strip() if pd.notna(prev_val) else ''
        curr_str = str(curr_val).strip() if pd.notna(curr_val) else ''

        # USE_PREV related if previous was empty and current has value
        return (prev_str == '' or prev_str == 'nan') and (curr_str != '' and curr_str != 'nan')

    def categorize_change_importance(self, column_name: str, prev_val: Any, curr_val: Any) -> str:
        """
        Categorize changes as 'primary' or 'secondary' based on importance.

        Returns:
            'secondary' if the change is USE_PREV related (backfilled data)
            'primary' for all other changes (actual data changes that need investigation)
        """
        if self.is_use_prev_related_change(column_name, prev_val, curr_val):
            return 'secondary'
        return 'primary'

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

    def find_data_changes_detailed(self) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame],
    Dict[str, pd.DataFrame], Dict[str, pd.DataFrame]]:
        """
        Find changes in existing symbol/exchange pairs and organize by column and importance.

        Returns:
            Tuple of (summary_df, all_column_changes, primary_column_changes, secondary_column_changes)
        """
        common_keys = self.previous_keys & self.current_keys

        if not common_keys:
            logger.info("No common keys found for comparison")
            return pd.DataFrame(), {}, {}, {}

        # Create indexed DataFrames for efficient comparison
        prev_indexed = self.previous_df.set_index('composite_key')
        curr_indexed = self.current_df.set_index('composite_key')

        # Track changes by column and importance
        all_column_changes = defaultdict(list)
        primary_column_changes = defaultdict(list)
        secondary_column_changes = defaultdict(list)
        summary_changes = []

        logger.info(f"Comparing {len(common_keys)} common records for data changes...")
        logger.info(f"Ignoring columns: {sorted(list(config.IGNORE_COLUMNS))}")

        ignored_due_to_numeric = 0
        total_comparisons = 0
        primary_changes_count = 0
        secondary_changes_count = 0

        for i, key in enumerate(common_keys):
            if i % 5000 == 0:  # Progress indicator
                logger.info(f"Processed {i}/{len(common_keys)} records")

            try:
                prev_row = prev_indexed.loc[key]
                curr_row = curr_indexed.loc[key]

                symbol, exchange = key.split(':', 1)

                # Find differences
                row_changes = {}
                primary_fields = []
                secondary_fields = []

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

                            # Categorize change importance
                            importance = self.categorize_change_importance(col, prev_val, curr_val)

                            row_changes[col] = {
                                'previous_value': prev_display,
                                'current_value': curr_display,
                                'original_previous': str(prev_val) if pd.notna(prev_val) else '',
                                'original_current': str(curr_val) if pd.notna(curr_val) else '',
                                'importance': importance
                            }

                            if importance == 'primary':
                                primary_fields.append(col)
                                primary_changes_count += 1
                            else:
                                secondary_fields.append(col)
                                secondary_changes_count += 1

                            # Create change record for column tracking
                            change_record = {
                                'symbol': symbol,
                                'exchange': exchange,
                                'composite_key': key,
                                'previous_value': prev_display,
                                'current_value': curr_display,
                                'original_previous_value': str(prev_val) if pd.notna(prev_val) else '',
                                'original_current_value': str(curr_val) if pd.notna(curr_val) else '',
                                'is_numeric_column': col in config.NUMERIC_COLUMNS,
                                'is_use_prev_column': col in config.USE_PREV_COLUMNS,
                                'importance': importance,
                                'previous_date': self.previous_date,
                                'current_date': self.current_date,
                                'change_timestamp': datetime.now().isoformat()
                            }

                            # Add to appropriate tracking dictionaries
                            all_column_changes[col].append(change_record)

                            if importance == 'primary':
                                primary_column_changes[col].append(change_record)
                            else:
                                secondary_column_changes[col].append(change_record)

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
                        'primary_fields': ', '.join(sorted(primary_fields)),
                        'secondary_fields': ', '.join(sorted(secondary_fields)),
                        'primary_change_count': len(primary_fields),
                        'secondary_change_count': len(secondary_fields),
                        'total_change_count': len(row_changes),
                        'has_primary_changes': len(primary_fields) > 0,
                        'has_secondary_changes': len(secondary_fields) > 0,
                        'change_category': 'primary' if len(primary_fields) > 0 else 'secondary'
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
        all_column_dfs = {col: pd.DataFrame(changes) for col, changes in all_column_changes.items()}
        primary_column_dfs = {col: pd.DataFrame(changes) for col, changes in primary_column_changes.items()}
        secondary_column_dfs = {col: pd.DataFrame(changes) for col, changes in secondary_column_changes.items()}

        logger.info(f"Numeric normalizations prevented {ignored_due_to_numeric} false positives")
        logger.info(f"Found {len(summary_df)} records with data changes")
        logger.info(f"Primary changes: {primary_changes_count} field changes across {len(primary_column_dfs)} columns")
        logger.info(
            f"Secondary changes: {secondary_changes_count} field changes across {len(secondary_column_dfs)} columns")

        if summary_changes:
            # Log top changed columns by category
            primary_column_counts = [(col, len(df)) for col, df in primary_column_dfs.items()]
            secondary_column_counts = [(col, len(df)) for col, df in secondary_column_dfs.items()]

            primary_column_counts.sort(key=lambda x: x[1], reverse=True)
            secondary_column_counts.sort(key=lambda x: x[1], reverse=True)

            if primary_column_counts:
                logger.info("Top 5 PRIMARY changed columns:")
                for col, count in primary_column_counts[:5]:
                    logger.info(f"  {col}: {count} changes")

            if secondary_column_counts:
                logger.info("Top 5 SECONDARY changed columns:")
                for col, count in secondary_column_counts[:5]:
                    logger.info(f"  {col}: {count} changes")
        else:
            logger.info("No data changes found")

        return summary_df, all_column_dfs, primary_column_dfs, secondary_column_dfs

    def create_column_changes_summary(self, column_dfs: Dict[str, pd.DataFrame],
                                      output_prefix: str, category: str = "all") -> pd.DataFrame:
        """Create a summary of changes by column with importance categorization"""
        summary_data = []

        for column_name, changes_df in column_dfs.items():
            if changes_df.empty:
                continue

            # Analyze the types of changes in this column
            unique_changes = len(changes_df)
            unique_symbols = changes_df['symbol'].nunique()
            is_numeric = changes_df.iloc[0]['is_numeric_column'] if 'is_numeric_column' in changes_df.columns else False
            is_use_prev = changes_df.iloc[0][
                'is_use_prev_column'] if 'is_use_prev_column' in changes_df.columns else False
            importance = changes_df.iloc[0]['importance'] if 'importance' in changes_df.columns else 'unknown'

            # Get unique value transitions to understand the nature of changes
            transitions = changes_df[['previous_value', 'current_value']].drop_duplicates()
            unique_transitions = len(transitions)

            # Sample some changes for preview
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

            # Determine output file location based on importance
            if category == "primary":
                output_file = f"{output_prefix}_primary_column_{column_name}_changes.csv"
            elif category == "secondary":
                output_file = f"{output_prefix}_secondary_column_{column_name}_changes.csv"
            else:
                output_file = f"{output_prefix}_column_{column_name}_changes.csv"

            summary_data.append({
                'column_name': column_name,
                'importance': importance,
                'is_numeric': is_numeric,
                'is_use_prev': is_use_prev,
                'total_changes': unique_changes,
                'affected_symbols': unique_symbols,
                'unique_transitions': unique_transitions,
                'sample_changes': str(sample_data),
                'category': category,
                'output_file': output_file
            })

        return pd.DataFrame(summary_data).sort_values(['importance', 'total_changes'], ascending=[False, False])

    def generate_comparison_summary(self) -> Dict[str, Any]:
        """Generate a comprehensive summary of all changes including USE_PREV analysis"""
        new_entries = self.find_new_entries()
        missing_entries = self.find_missing_entries()
        data_changes_summary, all_column_changes, primary_column_changes, secondary_column_changes = self.find_data_changes_detailed()

        # Create column summaries by importance
        all_column_summary = self.create_column_changes_summary(all_column_changes,
                                                                f"comparison_{self.previous_date}_to_{self.current_date}",
                                                                "all")
        primary_column_summary = self.create_column_changes_summary(primary_column_changes,
                                                                    f"comparison_{self.previous_date}_to_{self.current_date}",
                                                                    "primary")
        secondary_column_summary = self.create_column_changes_summary(secondary_column_changes,
                                                                      f"comparison_{self.previous_date}_to_{self.current_date}",
                                                                      "secondary")

        # Count primary vs secondary changes
        primary_symbols = len(data_changes_summary[data_changes_summary.get('has_primary_changes',
                                                                            False) == True]) if not data_changes_summary.empty else 0
        secondary_only_symbols = len(data_changes_summary[
                                         (data_changes_summary.get('has_primary_changes', False) == False) &
                                         (data_changes_summary.get('has_secondary_changes', False) == True)
                                         ]) if not data_changes_summary.empty else 0

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
            'primary_changes_symbols': primary_symbols,
            'secondary_only_changes_symbols': secondary_only_symbols,
            'use_prev_backfills': len(self.use_prev_changes_df),
            'columns_changed_count': len(all_column_changes),
            'primary_columns_changed_count': len(primary_column_changes),
            'secondary_columns_changed_count': len(secondary_column_changes),
            'total_changes': len(new_entries) + len(missing_entries) + len(data_changes_summary),
            'common_records': len(self.previous_keys & self.current_keys),
            'output_directory': str(self.output_dir),
            'primary_diff_directory': str(self.primary_diff_dir),
            'secondary_diff_directory': str(self.secondary_diff_dir),
            'updated_master_file': self.updated_master_file,
            'ignored_columns': sorted(list(config.IGNORE_COLUMNS)),
            'numeric_columns': sorted(list(config.NUMERIC_COLUMNS)),
            'use_prev_columns': sorted(list(config.USE_PREV_COLUMNS))
        }

        return (summary, new_entries, missing_entries, data_changes_summary,
                all_column_changes, primary_column_changes, secondary_column_changes,
                all_column_summary, primary_column_summary, secondary_column_summary)

    def save_results(self, output_prefix: str = None) -> Tuple[Dict[str, str], Dict[str, Any]]:
        """Save all comparison results to appropriate directories based on importance"""
        if output_prefix is None:
            output_prefix = f"comparison_{self.previous_date}_to_{self.current_date}"

        (summary, new_entries, missing_entries, data_changes_summary,
         all_column_changes, primary_column_changes, secondary_column_changes,
         all_column_summary, primary_column_summary, secondary_column_summary) = self.generate_comparison_summary()

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

        # Save USE_PREV changes summary
        if not self.use_prev_changes_df.empty:
            use_prev_file = self.output_dir / f"{output_prefix}_use_prev_changes.csv"
            self.use_prev_changes_df.to_csv(use_prev_file, index=False)
            output_files['use_prev_changes'] = str(use_prev_file)
            logger.info(f"Saved {len(self.use_prev_changes_df)} USE_PREV changes to {use_prev_file}")

        # Save data changes summary (contains both primary and secondary)
        if not data_changes_summary.empty:
            changes_summary_file = self.output_dir / f"{output_prefix}_data_changes_summary.csv"
            data_changes_summary.to_csv(changes_summary_file, index=False)
            output_files['data_changes_summary'] = str(changes_summary_file)
            logger.info(f"Saved {len(data_changes_summary)} data change summaries to {changes_summary_file}")

        # Save column summaries
        if not all_column_summary.empty:
            all_column_summary_file = self.output_dir / f"{output_prefix}_columns_summary.csv"
            all_column_summary.to_csv(all_column_summary_file, index=False)
            output_files['all_columns_summary'] = str(all_column_summary_file)
            logger.info(f"Saved all columns summary to {all_column_summary_file}")

        if not primary_column_summary.empty:
            primary_summary_file = self.output_dir / f"{output_prefix}_primary_columns_summary.csv"
            primary_column_summary.to_csv(primary_summary_file, index=False)
            output_files['primary_columns_summary'] = str(primary_summary_file)
            logger.info(f"Saved primary columns summary to {primary_summary_file}")

        if not secondary_column_summary.empty:
            secondary_summary_file = self.output_dir / f"{output_prefix}_secondary_columns_summary.csv"
            secondary_column_summary.to_csv(secondary_summary_file, index=False)
            output_files['secondary_columns_summary'] = str(secondary_summary_file)
            logger.info(f"Saved secondary columns summary to {secondary_summary_file}")

        # Save PRIMARY column-specific changes (important data changes)
        primary_files_created = 0
        for column_name, changes_df in primary_column_changes.items():
            if changes_df.empty:
                continue

            clean_column_name = column_name.replace('/', '_').replace(' ', '_').replace('|', '_')
            column_file = self.primary_diff_dir / f"{output_prefix}_primary_column_{clean_column_name}_changes.csv"
            changes_df.to_csv(column_file, index=False)
            output_files[f'primary_column_{clean_column_name}'] = str(column_file)
            primary_files_created += 1

        logger.info(f"Saved {primary_files_created} PRIMARY column-specific change files")

        # Save SECONDARY column-specific changes (USE_PREV related changes)
        secondary_files_created = 0
        for column_name, changes_df in secondary_column_changes.items():
            if changes_df.empty:
                continue

            clean_column_name = column_name.replace('/', '_').replace(' ', '_').replace('|', '_')
            column_file = self.secondary_diff_dir / f"{output_prefix}_secondary_column_{clean_column_name}_changes.csv"
            changes_df.to_csv(column_file, index=False)
            output_files[f'secondary_column_{clean_column_name}'] = str(column_file)
            secondary_files_created += 1

        logger.info(f"Saved {secondary_files_created} SECONDARY column-specific change files")

        # Save comprehensive summary with USE_PREV and categorization info
        summary_file = self.output_dir / f"{output_prefix}_summary.txt"
        with open(summary_file, 'w') as f:
            f.write("MASTER FILE COMPARISON SUMMARY WITH USE_PREV FUNCTIONALITY\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Comparison: {self.previous_date} -> {self.current_date}\n")
            f.write(f"Main Output Directory: {self.output_dir}\n")
            f.write(f"Primary Diff Directory: {self.primary_diff_dir}\n")
            f.write(f"Secondary Diff Directory: {self.secondary_diff_dir}\n")
            if summary['updated_master_file']:
                f.write(f"Updated Master File: {summary['updated_master_file']}\n")
            f.write("\n")

            f.write("CONFIGURATION:\n")
            f.write("-" * 30 + "\n")
            f.write(
                f"Ignored Columns ({len(config.IGNORE_COLUMNS)}): {', '.join(sorted(list(config.IGNORE_COLUMNS)))}\n")
            f.write(
                f"Numeric Columns ({len(config.NUMERIC_COLUMNS)}): {', '.join(sorted(list(config.NUMERIC_COLUMNS)))}\n")
            f.write(
                f"USE_PREV Columns ({len(config.USE_PREV_COLUMNS)}): {', '.join(sorted(list(config.USE_PREV_COLUMNS)))}\n\n")

            f.write("OVERVIEW:\n")
            f.write("-" * 20 + "\n")
            for key, value in summary.items():
                if key not in ['ignored_columns', 'numeric_columns', 'use_prev_columns']:  # Already shown above
                    f.write(f"{key}: {value}\n")
            f.write("\n")

            # Add detailed breakdown with USE_PREV context
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

            if summary['use_prev_backfills'] > 0:
                f.write(f"🔄 USE_PREV BACKFILLS ({summary['use_prev_backfills']})\n")
                f.write("   - Empty fields filled with previous day's data\n")
                f.write(f"   - File: {Path(output_files.get('use_prev_changes', 'N/A')).name}\n")
                f.write(
                    f"   - Updated Master: {Path(summary['updated_master_file']).name if summary['updated_master_file'] else 'N/A'}\n\n")

            if summary['data_changes_count'] > 0:
                f.write(f"📊 DATA CHANGES ({summary['data_changes_count']} symbols)\n")
                f.write(
                    f"   - PRIMARY Changes: {summary['primary_changes_symbols']} symbols (requires investigation)\n")
                f.write(
                    f"   - SECONDARY Only: {summary['secondary_only_changes_symbols']} symbols (USE_PREV related)\n")
                f.write("   - Numeric values normalized for comparison (30.0 = 30)\n")
                f.write(f"   - Summary: {Path(output_files.get('data_changes_summary', 'N/A')).name}\n")

                if summary['primary_changes_symbols'] > 0:
                    f.write(f"   - PRIMARY Changes saved to: {self.primary_diff_dir.name}/\n")
                    if not primary_column_summary.empty:
                        f.write("   - Top PRIMARY Changed Columns:\n")
                        for _, row in primary_column_summary.head(5).iterrows():
                            numeric_flag = " (numeric)" if row.get('is_numeric', False) else ""
                            f.write(f"     • {row['column_name']}{numeric_flag}: {row['total_changes']} changes\n")

                if summary['secondary_only_changes_symbols'] > 0:
                    f.write(f"   - SECONDARY Changes saved to: {self.secondary_diff_dir.name}/\n")
                    if not secondary_column_summary.empty:
                        f.write("   - Top SECONDARY Changed Columns (USE_PREV related):\n")
                        for _, row in secondary_column_summary.head(5).iterrows():
                            use_prev_flag = " (USE_PREV)" if row.get('is_use_prev', False) else ""
                            f.write(f"     • {row['column_name']}{use_prev_flag}: {row['total_changes']} changes\n")

                f.write("\n")

            f.write(f"📊 TOTAL CHANGES: {summary['total_changes']}\n\n")

            f.write("DIRECTORY STRUCTURE:\n")
            f.write("-" * 30 + "\n")
            f.write(f"diff/                    <- Summary files, new/missing entries\n")
            f.write(f"diff/primary/            <- Important data changes requiring investigation\n")
            f.write(f"diff/secondary/          <- USE_PREV related changes (less critical)\n\n")

            f.write("KEY FILES GENERATED:\n")
            f.write("-" * 30 + "\n")
            for file_type, file_path in output_files.items():
                location = "📁 main" if "/primary/" not in file_path and "/secondary/" not in file_path else (
                    "🚨 primary" if "/primary/" in file_path else "🔄 secondary")
                f.write(f"{location} | {file_type}: {Path(file_path).name}\n")

        output_files['summary'] = str(summary_file)
        logger.info(f"Saved comprehensive summary to {summary_file}")

        return output_files, summary