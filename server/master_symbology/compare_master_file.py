#!/usr/bin/env python3
"""
Master File Comparison Script

This script compares two master symbology files using (symbol, exchange) pairs as unique identifiers.
The same symbol can exist on multiple exchanges (e.g., AAPL on NASDAQ vs AAPL on NYSE).

Usage:
    python compare_master_files.py file1.csv file2.csv
    python compare_master_files.py --auto  # Compare latest two files
    python compare_master_files.py --date 20250829  # Compare with previous day
"""

import pandas as pd
import argparse
import os
import json
from datetime import datetime, timedelta


def load_master_file(file_path):
    """Load master file with proper handling of pipe delimiter"""
    try:
        df = pd.read_csv(file_path, sep='|', dtype=str)
        df = df.fillna('')  # Replace NaN with empty string for comparison

        # Validate required columns
        if 'symbol' not in df.columns or 'exchange' not in df.columns:
            raise ValueError(f"Missing required columns 'symbol' or 'exchange' in {file_path}")

        return df
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return None


def find_latest_files(data_dir, count=2):
    """Find the latest master files in data directory"""
    master_files = sorted([
        f for f in os.listdir(data_dir)
        if f.endswith('_MASTER.csv')
    ], reverse=True)

    if len(master_files) < count:
        return None

    return [os.path.join(data_dir, f) for f in master_files[:count]]


def find_file_by_date(data_dir, date_str):
    """Find master file for specific date"""
    target_file = f"{date_str}_MASTER.csv"
    file_path = os.path.join(data_dir, target_file)

    if os.path.exists(file_path):
        return file_path
    return None


def create_comparison_key(df):
    """
    Create comparison key from (symbol, exchange) pair.
    This ensures we properly handle the same symbol on different exchanges.
    """
    if 'symbol' not in df.columns or 'exchange' not in df.columns:
        raise ValueError("DataFrame must contain 'symbol' and 'exchange' columns")

    # Create composite key: "SYMBOL:EXCHANGE"
    return df['symbol'].astype(str) + ':' + df['exchange'].astype(str)


def validate_uniqueness(df, file_name):
    """
    Validate that (symbol, exchange) pairs are unique in the dataframe.
    Report any duplicates found.
    """
    key_series = create_comparison_key(df)
    duplicates = key_series.duplicated()

    validation_result = {
        'file_name': file_name,
        'total_records': len(df),
        'unique_keys': key_series.nunique(),
        'duplicate_count': duplicates.sum(),
        'is_valid': duplicates.sum() == 0
    }

    if duplicates.sum() > 0:
        duplicate_keys = key_series[duplicates].unique()
        validation_result['duplicate_keys'] = duplicate_keys.tolist()
        print(f"⚠️  WARNING: Found {duplicates.sum()} duplicate (symbol, exchange) pairs in {file_name}")
        print(f"   Sample duplicates: {duplicate_keys[:5].tolist()}")

    return validation_result


def analyze_exchange_distribution(df1, df2, file1_name, file2_name):
    """Analyze how symbols are distributed across exchanges"""
    analysis = {}

    # Exchange distribution in each file
    analysis['file1_exchanges'] = df1['exchange'].value_counts().to_dict()
    analysis['file2_exchanges'] = df2['exchange'].value_counts().to_dict()

    # Changes in exchange distribution
    all_exchanges = set(df1['exchange'].unique()) | set(df2['exchange'].unique())
    exchange_changes = {}

    for exchange in all_exchanges:
        count1 = (df1['exchange'] == exchange).sum()
        count2 = (df2['exchange'] == exchange).sum()
        change = count2 - count1

        if change != 0:
            exchange_changes[exchange] = {
                'old_count': count1,
                'new_count': count2,
                'change': change,
                'change_percentage': (change / count1 * 100) if count1 > 0 else float('inf')
            }

    analysis['exchange_changes'] = exchange_changes

    return analysis


def find_cross_exchange_movements(df1, df2):
    """
    Find symbols that moved between exchanges.
    This identifies cases where the same symbol appears on different exchanges between files.
    """
    movements = []

    # Get symbols that appear in both files
    symbols1 = set(df1['symbol'].unique())
    symbols2 = set(df2['symbol'].unique())
    common_symbols = symbols1 & symbols2

    for symbol in common_symbols:
        exchanges1 = set(df1[df1['symbol'] == symbol]['exchange'].unique())
        exchanges2 = set(df2[df2['symbol'] == symbol]['exchange'].unique())

        # Check if the symbol's exchange set changed
        if exchanges1 != exchanges2:
            movements.append({
                'symbol': symbol,
                'old_exchanges': sorted(list(exchanges1)),
                'new_exchanges': sorted(list(exchanges2)),
                'added_to_exchanges': sorted(list(exchanges2 - exchanges1)),
                'removed_from_exchanges': sorted(list(exchanges1 - exchanges2))
            })

    return movements


def compare_dataframes(df1, df2, file1_name, file2_name):
    """
    Compare two master dataframes using (symbol, exchange) pairs as unique identifiers.

    Args:
        df1: First dataframe (typically older)
        df2: Second dataframe (typically newer)
        file1_name: Name of first file
        file2_name: Name of second file

    Returns:
        Dictionary containing comprehensive comparison results
    """
    results = {
        'file1_name': file1_name,
        'file2_name': file2_name,
        'comparison_timestamp': datetime.now().isoformat(),
    }

    # Validate uniqueness in both files
    validation1 = validate_uniqueness(df1, file1_name)
    validation2 = validate_uniqueness(df2, file2_name)
    results['validation'] = {
        'file1': validation1,
        'file2': validation2
    }

    # Basic stats
    results['file1_count'] = len(df1)
    results['file2_count'] = len(df2)
    results['count_change'] = len(df2) - len(df1)
    results['count_change_percentage'] = (results['count_change'] / len(df1) * 100) if len(df1) > 0 else 0

    # Create comparison keys using (symbol, exchange) pairs
    key1 = create_comparison_key(df1)
    key2 = create_comparison_key(df2)

    set1 = set(key1)
    set2 = set(key2)

    # Find additions, removals, and common pairs
    added_pairs = set2 - set1  # (symbol, exchange) pairs only in file2
    removed_pairs = set1 - set2  # (symbol, exchange) pairs only in file1
    common_pairs = set1 & set2  # (symbol, exchange) pairs in both files

    results['added_count'] = len(added_pairs)
    results['removed_count'] = len(removed_pairs)
    results['common_count'] = len(common_pairs)

    results['added_pairs'] = sorted(list(added_pairs))
    results['removed_pairs'] = sorted(list(removed_pairs))

    # Analyze exchange distribution changes
    exchange_analysis = analyze_exchange_distribution(df1, df2, file1_name, file2_name)
    results['exchange_analysis'] = exchange_analysis

    # Find cross-exchange movements
    cross_exchange_movements = find_cross_exchange_movements(df1, df2)
    results['cross_exchange_movements'] = cross_exchange_movements

    # Find data changes in common (symbol, exchange) pairs
    changes = []

    if common_pairs:
        # Create lookup dictionaries using (symbol, exchange) as key
        df1_lookup = df1.set_index(key1)
        df2_lookup = df2.set_index(key2)

        # Compare each common (symbol, exchange) pair
        for pair_key in common_pairs:
            row1 = df1_lookup.loc[pair_key]
            row2 = df2_lookup.loc[pair_key]

            # Find changed fields
            changed_fields = {}
            for col in df1.columns:
                if col in df2.columns and col not in ['symbol', 'exchange']:  # Skip key columns
                    val1 = str(row1[col]) if pd.notna(row1[col]) else ''
                    val2 = str(row2[col]) if pd.notna(row2[col]) else ''

                    if val1 != val2:
                        changed_fields[col] = {
                            'old_value': val1,
                            'new_value': val2
                        }

            if changed_fields:
                symbol, exchange = pair_key.split(':', 1)
                changes.append({
                    'symbol': symbol,
                    'exchange': exchange,
                    'pair_key': pair_key,
                    'changed_fields': changed_fields
                })

    results['changed_count'] = len(changes)
    results['changes'] = changes

    # Column schema analysis
    cols1 = set(df1.columns)
    cols2 = set(df2.columns)

    results['schema_changes'] = {
        'added_columns': sorted(list(cols2 - cols1)),
        'removed_columns': sorted(list(cols1 - cols2)),
        'common_columns': sorted(list(cols1 & cols2))
    }

    # Field-level change frequency analysis
    field_change_summary = {}
    for change in changes:
        for field, change_info in change['changed_fields'].items():
            if field not in field_change_summary:
                field_change_summary[field] = 0
            field_change_summary[field] += 1

    results['field_change_summary'] = field_change_summary

    # Symbol-level analysis (aggregated across exchanges)
    symbols1 = set(df1['symbol'].unique())
    symbols2 = set(df2['symbol'].unique())

    results['symbol_level_analysis'] = {
        'symbols_added': sorted(list(symbols2 - symbols1)),  # Completely new symbols
        'symbols_removed': sorted(list(symbols1 - symbols2)),  # Completely removed symbols
        'symbols_common': len(symbols1 & symbols2),
        'new_symbol_count': len(symbols2 - symbols1),
        'removed_symbol_count': len(symbols1 - symbols2)
    }

    return results


def generate_detailed_reports(results, output_dir):
    """Generate comprehensive reports from comparison results"""
    os.makedirs(output_dir, exist_ok=True)

    # Save full results as JSON
    json_file = os.path.join(output_dir, 'comparison_results.json')
    with open(json_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    # Generate human-readable summary
    summary_lines = []
    summary_lines.append(f"Master File Comparison Report")
    summary_lines.append(f"Generated: {results['comparison_timestamp']}")
    summary_lines.append("=" * 60)
    summary_lines.append("")

    summary_lines.append("FILES COMPARED:")
    summary_lines.append(f"  File 1 (older): {results['file1_name']}")
    summary_lines.append(f"  File 2 (newer): {results['file2_name']}")
    summary_lines.append("")

    # Data validation results
    summary_lines.append("DATA VALIDATION:")
    val1 = results['validation']['file1']
    val2 = results['validation']['file2']

    summary_lines.append(
        f"  File 1: {val1['total_records']:,} records, {val1['unique_keys']:,} unique (symbol,exchange) pairs")
    if not val1['is_valid']:
        summary_lines.append(f"    ⚠️  {val1['duplicate_count']} duplicate pairs found!")

    summary_lines.append(
        f"  File 2: {val2['total_records']:,} records, {val2['unique_keys']:,} unique (symbol,exchange) pairs")
    if not val2['is_valid']:
        summary_lines.append(f"    ⚠️  {val2['duplicate_count']} duplicate pairs found!")
    summary_lines.append("")

    summary_lines.append("RECORD COUNT CHANGES:")
    summary_lines.append(
        f"  Total pairs change: {results['count_change']:+,} ({results['count_change_percentage']:+.2f}%)")
    summary_lines.append("")

    summary_lines.append("(SYMBOL, EXCHANGE) PAIR CHANGES:")
    summary_lines.append(f"  Added pairs: {results['added_count']:,}")
    summary_lines.append(f"  Removed pairs: {results['removed_count']:,}")
    summary_lines.append(f"  Modified pairs: {results['changed_count']:,}")
    summary_lines.append(f"  Unchanged pairs: {results['common_count'] - results['changed_count']:,}")
    summary_lines.append("")

    # Exchange distribution analysis
    if results['exchange_analysis']['exchange_changes']:
        summary_lines.append("EXCHANGE-LEVEL CHANGES:")
        for exchange, change_info in results['exchange_analysis']['exchange_changes'].items():
            pct = change_info['change_percentage']
            if pct != float('inf'):
                summary_lines.append(
                    f"  {exchange}: {change_info['old_count']:,} → {change_info['new_count']:,} ({change_info['change']:+,}, {pct:+.1f}%)")
            else:
                summary_lines.append(
                    f"  {exchange}: {change_info['old_count']:,} → {change_info['new_count']:,} (new exchange)")
        summary_lines.append("")

    # Symbol-level changes (aggregated)
    symbol_analysis = results['symbol_level_analysis']
    summary_lines.append("SYMBOL-LEVEL CHANGES (across all exchanges):")
    summary_lines.append(f"  Completely new symbols: {symbol_analysis['new_symbol_count']:,}")
    summary_lines.append(f"  Completely removed symbols: {symbol_analysis['removed_symbol_count']:,}")
    summary_lines.append("")

    # Cross-exchange movements
    if results['cross_exchange_movements']:
        summary_lines.append("CROSS-EXCHANGE MOVEMENTS:")
        summary_lines.append(f"  Symbols that changed exchanges: {len(results['cross_exchange_movements'])}")
        for movement in results['cross_exchange_movements'][:5]:  # Show first 5
            summary_lines.append(f"    {movement['symbol']}: {movement['old_exchanges']} → {movement['new_exchanges']}")
        if len(results['cross_exchange_movements']) > 5:
            summary_lines.append(f"    ... and {len(results['cross_exchange_movements']) - 5} more")
        summary_lines.append("")

    # Schema changes
    if results['schema_changes']['added_columns']:
        summary_lines.append("NEW COLUMNS:")
        for col in results['schema_changes']['added_columns']:
            summary_lines.append(f"  + {col}")
        summary_lines.append("")

    if results['schema_changes']['removed_columns']:
        summary_lines.append("REMOVED COLUMNS:")
        for col in results['schema_changes']['removed_columns']:
            summary_lines.append(f"  - {col}")
        summary_lines.append("")

    # Field change frequency
    if results['field_change_summary']:
        summary_lines.append("MOST FREQUENTLY CHANGED FIELDS:")
        sorted_fields = sorted(results['field_change_summary'].items(), key=lambda x: x[1], reverse=True)
        for field, count in sorted_fields[:10]:
            summary_lines.append(f"  {field}: {count:,} changes")
        summary_lines.append("")

    # Sample additions and removals (showing symbol:exchange format)
    if results['added_pairs']:
        summary_lines.append("SAMPLE ADDED (SYMBOL, EXCHANGE) PAIRS:")
        for pair in results['added_pairs'][:20]:
            summary_lines.append(f"  + {pair}")
        if len(results['added_pairs']) > 20:
            summary_lines.append(f"  ... and {len(results['added_pairs']) - 20} more")
        summary_lines.append("")

    if results['removed_pairs']:
        summary_lines.append("SAMPLE REMOVED (SYMBOL, EXCHANGE) PAIRS:")
        for pair in results['removed_pairs'][:20]:
            summary_lines.append(f"  - {pair}")
        if len(results['removed_pairs']) > 20:
            summary_lines.append(f"  ... and {len(results['removed_pairs']) - 20} more")
        summary_lines.append("")

    # Save summary
    summary_file = os.path.join(output_dir, 'comparison_summary.txt')
    with open(summary_file, 'w') as f:
        f.write('\n'.join(summary_lines))

    # Save detailed lists
    if results['added_pairs']:
        added_file = os.path.join(output_dir, 'added_pairs.txt')
        with open(added_file, 'w') as f:
            f.write("# Added (Symbol, Exchange) Pairs\n")
            f.write("# Format: SYMBOL:EXCHANGE\n\n")
            f.write('\n'.join(results['added_pairs']))

    if results['removed_pairs']:
        removed_file = os.path.join(output_dir, 'removed_pairs.txt')
        with open(removed_file, 'w') as f:
            f.write("# Removed (Symbol, Exchange) Pairs\n")
            f.write("# Format: SYMBOL:EXCHANGE\n\n")
            f.write('\n'.join(results['removed_pairs']))

    # Save cross-exchange movements
    if results['cross_exchange_movements']:
        movements_file = os.path.join(output_dir, 'cross_exchange_movements.txt')
        with open(movements_file, 'w') as f:
            f.write("SYMBOLS THAT MOVED BETWEEN EXCHANGES:\n")
            f.write("=" * 40 + "\n\n")

            for movement in results['cross_exchange_movements']:
                f.write(f"Symbol: {movement['symbol']}\n")
                f.write(f"  Old exchanges: {movement['old_exchanges']}\n")
                f.write(f"  New exchanges: {movement['new_exchanges']}\n")
                if movement['added_to_exchanges']:
                    f.write(f"  Added to: {movement['added_to_exchanges']}\n")
                if movement['removed_from_exchanges']:
                    f.write(f"  Removed from: {movement['removed_from_exchanges']}\n")
                f.write("\n")

    # Save detailed changes
    if results['changes']:
        changes_file = os.path.join(output_dir, 'detailed_changes.txt')
        with open(changes_file, 'w') as f:
            f.write("DETAILED FIELD CHANGES BY (SYMBOL, EXCHANGE) PAIR:\n")
            f.write("=" * 50 + "\n\n")

            for change in results['changes']:
                f.write(f"Symbol: {change['symbol']} | Exchange: {change['exchange']}\n")
                for field, change_info in change['changed_fields'].items():
                    f.write(f"  {field}:\n")
                    f.write(f"    Old: {change_info['old_value']}\n")
                    f.write(f"    New: {change_info['new_value']}\n")
                f.write("\n")

    # Print summary to console
    print('\n'.join(summary_lines))
    print(f"\nDetailed reports saved to: {output_dir}")


def main():
    parser = argparse.ArgumentParser(description='Compare two master symbology files using (symbol, exchange) pairs')
    parser.add_argument('files', nargs='*', help='Two files to compare')
    parser.add_argument('--auto', action='store_true', help='Compare latest two files automatically')
    parser.add_argument('--date', help='Compare specific date with previous day (format: YYYYMMDD)')
    parser.add_argument('--data-dir', default=None, help='Data directory path')
    parser.add_argument('--output-dir', default=None, help='Output directory for comparison reports')

    args = parser.parse_args()

    # Determine data directory
    if args.data_dir:
        data_dir = args.data_dir
    else:
        # Default to ../data relative to script location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(script_dir, '..', 'data')

    if not os.path.exists(data_dir):
        print(f"Error: Data directory not found: {data_dir}")
        return 1

    # Determine files to compare
    file1_path = None
    file2_path = None

    if args.auto:
        # Find latest two files
        latest_files = find_latest_files(data_dir, 2)
        if not latest_files:
            print("Error: Could not find two master files for comparison")
            return 1
        file1_path, file2_path = latest_files[1], latest_files[0]  # older, newer

    elif args.date:
        # Compare specific date with previous day
        date_obj = datetime.strptime(args.date, '%Y%m%d')
        prev_date_obj = date_obj - timedelta(days=1)

        file2_path = find_file_by_date(data_dir, args.date)
        file1_path = find_file_by_date(data_dir, prev_date_obj.strftime('%Y%m%d'))

        if not file2_path:
            print(f"Error: Could not find master file for date {args.date}")
            return 1
        if not file1_path:
            print(f"Error: Could not find master file for previous date {prev_date_obj.strftime('%Y%m%d')}")
            return 1

    elif len(args.files) == 2:
        # Use provided files
        file1_path, file2_path = args.files
        if not os.path.exists(file1_path):
            print(f"Error: File not found: {file1_path}")
            return 1
        if not os.path.exists(file2_path):
            print(f"Error: File not found: {file2_path}")
            return 1
    else:
        print("Error: Must specify either two files, --auto, or --date option")
        parser.print_help()
        return 1

    # Load files
    print(f"Loading {file1_path}...")
    df1 = load_master_file(file1_path)
    if df1 is None:
        return 1

    print(f"Loading {file2_path}...")
    df2 = load_master_file(file2_path)
    if df2 is None:
        return 1

    # Perform comparison
    print("Comparing files using (symbol, exchange) pairs as unique identifiers...")
    results = compare_dataframes(df1, df2,
                                 os.path.basename(file1_path),
                                 os.path.basename(file2_path))

    # Determine output directory
    if args.output_dir:
        output_dir = args.output_dir
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = os.path.join(data_dir, '..', 'comparisons', f'comparison_{timestamp}')

    # Generate reports
    generate_detailed_reports(results, output_dir)

    return 0


if __name__ == '__main__':
    exit(main())