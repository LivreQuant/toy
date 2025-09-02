#!/usr/bin/env python3
"""
Main script for comparing master files with proper numeric comparison
Output will be saved to /media/samaral/pro/alphastamp/master/YYYYMMDD/diff/
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
    # Create log file in the same diff directory
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
    """Print a formatted summary to console"""
    print("\n" + "=" * 70)
    print("MASTER FILE COMPARISON SUMMARY")
    print("=" * 70)
    print(f"Comparison: {summary['previous_date']} -> {summary['current_date']}")
    print(f"Output Directory: {summary['output_directory']}")
    print(f"Comparison Time: {summary['comparison_timestamp']}")
    print()
    print("CONFIGURATION:")
    print(f"  Ignored Columns: {len(summary['ignored_columns'])} columns")
    print(f"  Numeric Columns: {len(summary['numeric_columns'])} columns (30.0 = 30)")
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
    if summary['data_changes_count'] > 0:
        print(f"  🔄 Data Changes: {summary['data_changes_count']:,} symbols")
        print(f"  📋 Columns Changed: {summary['columns_changed_count']}")
    else:
        print(f"  🔄 Data Changes: 0")
    print(f"  📊 Total Changes: {summary['total_changes']:,}")
    print()

    if output_files:
        print("KEY OUTPUT FILES:")
        # Show the most important files first
        key_files = ['summary', 'columns_summary', 'data_changes_summary', 'new_entries', 'missing_entries']
        for file_type in key_files:
            if file_type in output_files:
                file_name = Path(output_files[file_type]).name
                print(f"  📄 {file_type.replace('_', ' ').title()}: {file_name}")

        # Count column-specific files
        column_files = [f for f in output_files.keys() if f.startswith('column_')]
        if column_files:
            print(f"  📊 Column-specific files: {len(column_files)} files")
            print(f"      (Format: comparison_YYYYMMDD_to_YYYYMMDD_column_X_changes.csv)")

    print("=" * 70)

    # Provide actionable insights
    if summary['total_changes'] == 0:
        print("✅ No changes detected between the files.")
    elif summary['columns_changed_count'] > 20:
        print("⚠️  Many columns changed. Review columns_summary.csv for overview.")
        print("💡 Consider adding frequently changing columns to IGNORE_COLUMNS in .env")
    elif summary['data_changes_count'] > 1000:
        print("⚠️  Large number of data changes. Review data_changes_summary.csv first.")
    else:
        print(f"ℹ️  {summary['total_changes']} changes detected. Check individual files for details.")

    print()


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='Compare master symbology files with proper numeric handling',
        epilog='Configure ignore and numeric columns in .env file. Output files will be saved to /media/samaral/pro/alphastamp/master/YYYYMMDD/diff/'
    )
    parser.add_argument('--date', help='Target date (YYYYMMDD). If not provided, uses today')
    parser.add_argument('--previous-file', help='Path to previous master file (overrides auto-detection)')
    parser.add_argument('--current-file', help='Path to current master file (overrides auto-detection)')
    parser.add_argument('--output-prefix', help='Prefix for output files')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        default=config.LOG_LEVEL, help='Logging level')
    parser.add_argument('--show-config', action='store_true',
                        help='Show current configuration and exit')

    args = parser.parse_args()

    # Show configuration if requested
    if args.show_config:
        print("CURRENT CONFIGURATION:")
        print("=" * 50)
        config_info = config.print_config()
        for key, value in config_info.items():
            if isinstance(value, list):
                print(f"{key}: {len(value)} items")
                for item in value:
                    print(f"  - {item}")
            else:
                print(f"{key}: {value}")
        print("=" * 50)
        return 0

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
        logger.info(f"Treating {len(config.NUMERIC_COLUMNS)} columns as numeric: {sorted(list(config.NUMERIC_COLUMNS))}")

        # Get master files
        if args.previous_file and args.current_file:
            # Manual file specification - extract dates if possible
            from source.master.utils import get_date_from_filename
            previous_date = get_date_from_filename(args.previous_file) or "unknown"
            current_date = get_date_from_filename(args.current_file) or target_date

            previous_file_info = (previous_date, args.previous_file)
            current_file_info = (current_date, args.current_file)
            logger.info("Using provided file paths")
        else:
            logger.info("Auto-detecting master files...")
            file_pair = get_master_file_pair(target_date)
            previous_file_info, current_file_info = file_pair

            if not previous_file_info or not current_file_info:
                logger.error("Could not find required master files")
                return 1

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

        # Create comparator and run comparison
        logger.info("Starting comparison with numeric normalization...")
        comparator = MasterFileComparator(previous_df, current_df, previous_date, current_date)

        # Generate output prefix
        output_prefix = args.output_prefix or f"comparison_{previous_date}_to_{current_date}"

        # Save results
        logger.info("Generating and saving results...")
        output_files, summary = comparator.save_results(output_prefix)

        # Print summary
        print_summary(summary, output_files)

        logger.info("Comparison completed successfully")
        logger.info(f"All output files saved to: {summary['output_directory']}")

        return 0

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())