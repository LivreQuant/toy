#!/usr/bin/env python3
"""
Main script for comparing master files with USE_PREV functionality
Output will be categorized into primary/secondary diff directories
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from config import config
from source.master.utils import get_master_file_pair, load_master_file
from source.master.compare import MasterFileComparator


def setup_logging(current_date: str, log_level: str = "INFO"):
    """Setup logging configuration"""
    # Create log file in the main diff directory
    log_dir = config.get_output_dir(current_date)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'master_comparison.log'

    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file)
        ]
    )


def print_summary(summary: dict, output_files: dict):
    """Print a formatted summary to console with USE_PREV information"""
    print("\n" + "=" * 80)
    print("MASTER FILE COMPARISON SUMMARY WITH USE_PREV FUNCTIONALITY")
    print("=" * 80)
    print(f"Comparison: {summary['previous_date']} -> {summary['current_date']}")
    print(f"Main Directory: {summary['output_directory']}")
    print(f"Primary Directory: {summary['primary_diff_directory']}")
    print(f"Secondary Directory: {summary['secondary_diff_directory']}")
    print(f"Comparison Time: {summary['comparison_timestamp']}")
    print()

    print("CONFIGURATION:")
    print(f"  Ignored Columns: {len(summary['ignored_columns'])} columns")
    print(f"  Numeric Columns: {len(summary['numeric_columns'])} columns (30.0 = 30)")
    print(f"  USE_PREV Columns: {len(summary['use_prev_columns'])} columns")
    print()

    print("FILE STATISTICS:")
    print(f"  Previous File Records: {summary['previous_file_records']:,}")
    print(f"  Current File Records: {summary['current_file_records']:,}")
    print(f"  Net Change: {summary['net_change']:+,}")
    print(f"  Common Records: {summary['common_records']:,}")
    print()

    print("CHANGES DETECTED:")
    print(f"  📈 New Entries: {summary['new_entries_count']:,}")
    print(f"  📉 Missing Entries: {summary['missing_entries_count']:,}")

    if summary['use_prev_backfills'] > 0:
        print(f"  🔄 USE_PREV Backfills: {summary['use_prev_backfills']:,} field updates")
        if summary['updated_master_file']:
            print(f"      Updated Master Created: {Path(summary['updated_master_file']).name}")

    if summary['data_changes_count'] > 0:
        print(f"  📊 Data Changes: {summary['data_changes_count']:,} symbols")
        print(f"      🚨 PRIMARY (Investigation Required): {summary['primary_changes_symbols']:,} symbols")
        print(f"      🔄 SECONDARY (USE_PREV Related): {summary['secondary_only_changes_symbols']:,} symbols")
        print(f"      📋 Total Columns Changed: {summary['columns_changed_count']}")
        print(f"      📋 Primary Columns: {summary['primary_columns_changed_count']}")
        print(f"      📋 Secondary Columns: {summary['secondary_columns_changed_count']}")
    else:
        print(f"  📊 Data Changes: 0")

    print(f"  📊 Total Changes: {summary['total_changes']:,}")
    print()

    if output_files:
        print("KEY OUTPUT FILES BY CATEGORY:")
        print("📁 MAIN DIRECTORY (Summary & Core Changes):")
        main_files = ['summary', 'new_entries', 'missing_entries', 'data_changes_summary',
                      'use_prev_changes', 'all_columns_summary']
        for file_type in main_files:
            if file_type in output_files:
                file_name = Path(output_files[file_type]).name
                print(f"      📄 {file_type.replace('_', ' ').title()}: {file_name}")

        # Count primary and secondary files
        primary_files = [f for f in output_files.keys() if 'primary_column_' in f]
        secondary_files = [f for f in output_files.keys() if 'secondary_column_' in f]

        if primary_files:
            print("🚨 PRIMARY DIRECTORY (Requires Investigation):")
            print(f"      📊 Column-specific files: {len(primary_files)} files")
            if 'primary_columns_summary' in output_files:
                print(f"      📄 Summary: {Path(output_files['primary_columns_summary']).name}")

        if secondary_files:
            print("🔄 SECONDARY DIRECTORY (USE_PREV Related):")
            print(f"      📊 Column-specific files: {len(secondary_files)} files")
            if 'secondary_columns_summary' in output_files:
                print(f"      📄 Summary: {Path(output_files['secondary_columns_summary']).name}")

    print("=" * 80)

    # Provide actionable insights with USE_PREV context
    if summary['total_changes'] == 0:
        print("✅ No changes detected between the files.")
    elif summary['primary_changes_symbols'] > 0:
        print("🚨 PRIORITY: Review PRIMARY directory files - these require investigation!")
        if summary['primary_changes_symbols'] > 100:
            print("💡 Start with primary_columns_summary.csv for overview of critical changes")
    elif summary['secondary_only_changes_symbols'] > 0:
        print("ℹ️  Only SECONDARY changes detected - these are USE_PREV backfills (less critical)")

    if summary['use_prev_backfills'] > 0:
        print(f"✅ USE_PREV processed: {summary['use_prev_backfills']} empty fields backfilled from previous day")
        if summary['updated_master_file']:
            print(f"📄 Updated master file created with backfilled data")

    if summary['columns_changed_count'] > 20:
        print("💡 Consider reviewing .env USE_PREV configuration if too many secondary changes")

    print()


def main():
    """Main execution function with USE_PREV functionality"""
    parser = argparse.ArgumentParser(
        description='Compare master symbology files with USE_PREV functionality and primary/secondary categorization',
        epilog='Configure ignore, numeric, and USE_PREV columns in .env file. '
               'Output: diff/ (summaries), diff/primary/ (critical changes), diff/secondary/ (USE_PREV related)'
    )
    parser.add_argument('--date', help='Target date (YYYYMMDD). If not provided, uses today')
    parser.add_argument('--previous-file', help='Path to previous master file (overrides auto-detection)')
    parser.add_argument('--current-file', help='Path to current master file (overrides auto-detection)')
    parser.add_argument('--output-prefix', help='Prefix for output files')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        default=config.LOG_LEVEL, help='Logging level')
    parser.add_argument('--show-config', action='store_true',
                        help='Show current configuration and exit')
    parser.add_argument('--disable-use-prev', action='store_true',
                        help='Disable USE_PREV functionality for this run')

    args = parser.parse_args()

    # Show configuration if requested
    if args.show_config:
        print("CURRENT CONFIGURATION:")
        print("=" * 60)
        config_info = config.print_config()
        for key, value in config_info.items():
            if isinstance(value, list):
                print(f"{key}: {len(value)} items")
                for item in value[:10]:  # Show first 10 items
                    print(f"  - {item}")
                if len(value) > 10:
                    print(f"  ... and {len(value) - 10} more")
            else:
                print(f"{key}: {value}")
        print("=" * 60)
        return 0

    # Temporarily disable USE_PREV if requested
    if args.disable_use_prev:
        original_use_prev = config.USE_PREV_COLUMNS
        config.USE_PREV_COLUMNS = set()
        print("⚠️  USE_PREV functionality disabled for this run")

    # Determine target date early for logging setup
    target_date = args.date or datetime.now().strftime('%Y%m%d')

    # Setup logging
    setup_logging(target_date, args.log_level)
    logger = logging.getLogger(__name__)

    try:
        # Validate configuration
        config.validate_config()
        logger.info("Configuration validated successfully")
        logger.info(f"Target date: {target_date}")

        # Log configuration being used
        logger.info(f"Ignoring {len(config.IGNORE_COLUMNS)} columns: {sorted(list(config.IGNORE_COLUMNS))}")
        logger.info(
            f"Treating {len(config.NUMERIC_COLUMNS)} columns as numeric: {sorted(list(config.NUMERIC_COLUMNS))}")
        logger.info(
            f"USE_PREV enabled for {len(config.USE_PREV_COLUMNS)} columns: {sorted(list(config.USE_PREV_COLUMNS))}")

        # Get master files
        if args.previous_file and args.current_file:
            # Manual file specification - extract dates if possible
            from source.master.utils import get_date_from_filename
            previous_date = get_date_from_filename(args.previous_file) or "unknown"
            current_date = get_date_from_filename(args.current_file) or target_date

            previous_file_info = (previous_date, args.previous_file)
            current_file_info = (current_date, args.current_file)
            original_current_filename = args.current_file
            logger.info("Using provided file paths")
        else:
            logger.info("Auto-detecting master files...")
            file_pair = get_master_file_pair(target_date)
            previous_file_info, current_file_info = file_pair

            if not previous_file_info or not current_file_info:
                logger.error("Could not find required master files")
                return 1

            original_current_filename = current_file_info[1]

        previous_date, previous_file = previous_file_info
        current_date, current_file = current_file_info

        logger.info(f"Previous file ({previous_date}): {previous_file}")
        logger.info(f"Current file ({current_date}): {current_file}")

        # Load the files
        logger.info("Loading master files...")
        previous_df = load_master_file(previous_file)
        current_df = load_master_file(current_file)

        if previous_df is None or current_df is None:
            logger.error("Failed to load master files")
            return 1

        # Create comparator and run comparison with USE_PREV functionality
        logger.info("Starting comparison with USE_PREV functionality and importance categorization...")
        comparator = MasterFileComparator(previous_df, current_df, previous_date, current_date,
                                          original_current_filename)

        # Generate output prefix
        output_prefix = args.output_prefix or f"comparison_{previous_date}_to_{current_date}"

        # Save results
        logger.info("Generating and saving results...")
        output_files, summary = comparator.save_results(output_prefix)

        # Print summary
        print_summary(summary, output_files)

        logger.info("Comparison completed successfully")
        logger.info(f"Main output files saved to: {summary['output_directory']}")
        logger.info(f"Primary changes saved to: {summary['primary_diff_directory']}")
        logger.info(f"Secondary changes saved to: {summary['secondary_diff_directory']}")

        if summary['updated_master_file']:
            logger.info(f"Updated master file created: {summary['updated_master_file']}")

        return 0

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1

    finally:
        # Restore USE_PREV configuration if it was disabled
        if args.disable_use_prev:
            config.USE_PREV_COLUMNS = original_use_prev

if __name__ == "__main__":
    exit(main())