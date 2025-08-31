#!/usr/bin/env python3
"""
Data Changes Analyzer - Analyzes changes in existing symbols between two files
Includes data quality validation since we don't trust the data sources
"""

import pandas as pd
import argparse
import os
from datetime import datetime


def load_master_file(file_path):
    """Load master symbology file"""
    try:
        df = pd.read_csv(file_path, sep='|', dtype=str)
        df = df.fillna('')
        return df
    except Exception as e:
        print(f"❌ Error loading {file_path}: {e}")
        return None


def quick_data_quality_check(ca_dir, date_str):
    """Quick check of corporate actions data quality"""

    issues = []
    ca_files = ['delistings.csv', 'mergers.csv', 'symbol_changes.csv', 'stock_splits.csv', 'ipos.csv', 'spinoffs.csv',
                'rights.csv']

    for ca_file in ca_files:
        path = f"{ca_dir}/{ca_file}"
        if not os.path.exists(path):
            issues.append(f"❌ MISSING: {ca_file}")
            continue

        try:
            df = pd.read_csv(path)
            if len(df) == 0:
                issues.append(f"⚠️  EMPTY: {ca_file}")
            else:
                # Check for date columns and coverage
                date_cols = [col for col in df.columns if 'date' in col.lower()]
                if not date_cols:
                    issues.append(f"⚠️  NO DATE COLUMN: {ca_file}")
                else:
                    # Check if we have data for target date
                    date_col = date_cols[0]
                    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                    target_date = pd.to_datetime(date_str)

                    records_for_date = (df[date_col] == target_date).sum()
                    total_records = len(df)

                    if records_for_date == 0:
                        issues.append(f"⚠️  NO DATA FOR {date_str}: {ca_file} (has {total_records} total records)")
                    else:
                        issues.append(
                            f"✅ {ca_file}: {records_for_date} records for {date_str} (of {total_records} total)")

        except Exception as e:
            issues.append(f"❌ ERROR READING {ca_file}: {e}")

    return issues


def load_corporate_actions(ca_dir, date_str):
    """Load relevant corporate actions files with validation"""
    corporate_actions = {}

    # Load stock splits
    try:
        splits = pd.read_csv(f"{ca_dir}/stock_splits.csv")
        splits['ex_date'] = pd.to_datetime(splits['ex_date'], errors='coerce')
        target_date = pd.to_datetime(date_str)
        splits = splits[splits['ex_date'] == target_date]
        corporate_actions['splits'] = splits
    except:
        corporate_actions['splits'] = pd.DataFrame()

    # Load symbol changes (for CUSIP/name changes)
    try:
        symbol_changes = pd.read_csv(f"{ca_dir}/symbol_changes.csv")
        symbol_changes['change_date'] = pd.to_datetime(symbol_changes['change_date'], errors='coerce')
        target_date = pd.to_datetime(date_str)
        symbol_changes = symbol_changes[symbol_changes['change_date'] == target_date]
        corporate_actions['symbol_changes'] = symbol_changes
    except:
        corporate_actions['symbol_changes'] = pd.DataFrame()

    # Load mergers (can cause CUSIP changes)
    try:
        mergers = pd.read_csv(f"{ca_dir}/mergers.csv")
        mergers['ex_date'] = pd.to_datetime(mergers['ex_date'], errors='coerce')
        target_date = pd.to_datetime(date_str)
        mergers = mergers[mergers['ex_date'] == target_date]
        corporate_actions['mergers'] = mergers
    except:
        corporate_actions['mergers'] = pd.DataFrame()

    return corporate_actions


def analyze_data_changes(old_df, new_df, corporate_actions, data_quality_issues):
    """Find data changes in existing symbols"""

    # Create composite keys and find common symbols
    old_df['composite_key'] = old_df['symbol'] + ':' + old_df['exchange']
    new_df['composite_key'] = new_df['symbol'] + ':' + new_df['exchange']

    old_keys = set(old_df['composite_key'])
    new_keys = set(new_df['composite_key'])
    common_keys = old_keys & new_keys

    # Filter to common symbols
    old_common = old_df[old_df['composite_key'].isin(common_keys)].set_index('composite_key')
    new_common = new_df[new_df['composite_key'].isin(common_keys)].set_index('composite_key')

    # Columns to ignore (expected to change daily)
    ignore_columns = {
        'market_capital', 'scalemarketcap', 'earnings_announcement',
        'shares_outstanding', 'share_class_shares_outstanding',
        'weighted_shares_outstanding', 'composite_key'
    }

    # Columns that indicate significant corporate actions
    significant_columns = {
        'cusips', 'isin', 'name', 'type', 'primary_listing', 'status'
    }

    results = []

    print(f"Analyzing {len(common_keys)} common symbols for data changes")
    print("-" * 60)

    # Check if we have critical data issues that might affect results
    critical_issues = [issue for issue in data_quality_issues if "❌" in issue or "ERROR" in issue]
    missing_data_warnings = [issue for issue in data_quality_issues if "NO DATA FOR" in issue]

    for composite_key in common_keys:
        try:
            old_row = old_common.loc[composite_key]
            new_row = new_common.loc[composite_key]
        except KeyError:
            continue  # Skip if data inconsistency

        symbol, exchange = composite_key.split(':', 1)

        # Find all changes
        changes = {}
        for col in old_row.index:
            if col in ignore_columns:
                continue
            if col in new_row.index:
                old_val = str(old_row[col])
                new_val = str(new_row[col])
                if old_val != new_val:
                    changes[col] = {
                        'old_value': old_val,
                        'new_value': new_val
                    }

        if changes:
            # Try to explain the changes
            explanation = "UNEXPLAINED - Requires investigation"
            confidence = 0.0
            change_type = "unknown"
            data_quality_concern = False

            # Check for CUSIP changes
            if 'cusips' in changes:
                # Check if this matches a symbol change or merger
                symbol_match = corporate_actions['symbol_changes'][
                    corporate_actions['symbol_changes']['master_symbol'] == symbol
                    ]
                if not symbol_match.empty:
                    old_cusip = symbol_match.iloc[0].get('old_cusip', '')
                    new_cusip = symbol_match.iloc[0].get('new_cusip', '')
                    explanation = f"CUSIP change due to corporate name/symbol change"
                    if old_cusip and new_cusip:
                        explanation += f" ({old_cusip} -> {new_cusip})"
                    confidence = 0.90
                    change_type = "cusip_change"

                # Check mergers
                elif not corporate_actions['mergers'].empty:
                    merger_match = corporate_actions['mergers'][
                        (corporate_actions['mergers']['acquirer_symbol'] == symbol) |
                        (corporate_actions['mergers']['acquiree_symbol'] == symbol)
                        ]
                    if not merger_match.empty:
                        explanation = "CUSIP change due to merger activity"
                        confidence = 0.85
                        change_type = "cusip_change"

                # If unexplained CUSIP change, check data quality
                if confidence == 0.0:
                    if any("symbol_changes.csv" in issue for issue in critical_issues):
                        explanation = "CUSIP change (symbol change data missing/corrupt)"
                        data_quality_concern = True
                    elif any("mergers.csv" in issue for issue in critical_issues):
                        explanation = "CUSIP change (merger data missing/corrupt)"
                        data_quality_concern = True
                    else:
                        explanation = "UNEXPLAINED CUSIP CHANGE - Critical investigation required"
                        change_type = "cusip_change"

            # Check for name changes
            if 'name' in changes and change_type == "unknown":
                symbol_match = corporate_actions['symbol_changes'][
                    corporate_actions['symbol_changes']['master_symbol'] == symbol
                    ]
                if not symbol_match.empty:
                    explanation = "Company name change"
                    confidence = 0.95
                    change_type = "name_change"
                else:
                    if any("symbol_changes.csv" in issue for issue in critical_issues):
                        explanation = "Name change (symbol change data missing/corrupt)"
                        data_quality_concern = True
                    else:
                        explanation = "UNEXPLAINED NAME CHANGE - Investigation required"
                        change_type = "name_change"

            # Check for shares outstanding changes (potential split)
            shares_columns = [col for col in changes.keys() if 'shares' in col.lower() and col not in ignore_columns]
            if shares_columns and change_type == "unknown":
                split_match = corporate_actions['splits'][
                    corporate_actions['splits']['master_symbol'] == symbol
                    ]
                if not split_match.empty:
                    ratio = split_match.iloc[0].get('split_ratio', 1)
                    split_type = "forward" if ratio > 1 else "reverse"
                    explanation = f"Shares adjusted for {ratio}:1 {split_type} stock split"
                    confidence = 0.90
                    change_type = "split_adjustment"
                else:
                    # Check if this might be due to missing split data
                    if any("stock_splits.csv" in issue for issue in critical_issues):
                        explanation = "Shares outstanding change (split data missing/corrupt)"
                        data_quality_concern = True
                    else:
                        explanation = "UNEXPLAINED SHARES CHANGE - Possible unreported split"
                        change_type = "shares_change"

            # Check for status changes
            if 'status' in changes and change_type == "unknown":
                old_status = changes['status']['old_value']
                new_status = changes['status']['new_value']

                # Common status transitions
                normal_transitions = [
                    ('Normal', 'Suspended'), ('Suspended', 'Normal'),
                    ('Normal', 'Deficient'), ('Deficient', 'Normal'),
                    ('Deficient', 'Suspended'), ('Suspended', 'Deficient')
                ]

                if (old_status, new_status) in normal_transitions:
                    explanation = f"Normal status change: {old_status} -> {new_status}"
                    confidence = 0.70
                    change_type = "status_change"
                else:
                    explanation = f"UNUSUAL STATUS CHANGE: {old_status} -> {new_status} - Investigation required"
                    change_type = "status_change"

            # Handle multiple changes
            if len(changes) > 1:
                change_types = list(changes.keys())
                significant_changes = [c for c in change_types if c in significant_columns]

                if len(significant_changes) > 1:
                    if confidence > 0:
                        explanation += f" (Multiple changes: {', '.join(significant_changes)})"
                    else:
                        explanation = f"MULTIPLE SIGNIFICANT CHANGES: {', '.join(significant_changes)} - Priority investigation"
                        change_type = "multiple_changes"

            # If still unexplained, provide context about data quality
            if confidence == 0.0 and not data_quality_concern:
                potential_issues = []

                if any("symbol_changes.csv" in issue for issue in missing_data_warnings):
                    potential_issues.append("no symbol change data for this date")
                if any("stock_splits.csv" in issue for issue in missing_data_warnings):
                    potential_issues.append("no split data for this date")
                if any("mergers.csv" in issue for issue in missing_data_warnings):
                    potential_issues.append("no merger data for this date")

                if potential_issues:
                    explanation += f" (Possible causes: {'; '.join(potential_issues)})"
                    data_quality_concern = True

            result = {
                'symbol': symbol,
                'exchange': exchange,
                'change_type': change_type,
                'changes_count': len(changes),
                'changed_fields': ', '.join(changes.keys()),
                'significant_changes': ', '.join([c for c in changes.keys() if c in significant_columns]),
                'explanation': explanation,
                'confidence': confidence,
                'data_quality_concern': data_quality_concern,
                'details': str(changes)  # Convert to string for CSV storage
            }
            results.append(result)

            status = "✅" if confidence > 0.8 else "❓" if confidence > 0.5 else "🚨"
            concern_flag = " ⚠️" if data_quality_concern else ""
            print(f"{status} {symbol}:{exchange} - {len(changes)} changes - {explanation}{concern_flag}")

            # Show details for significant changes
            if any(field in significant_columns for field in changes.keys()) or len(changes) <= 3:
                for field, change in changes.items():
                    print(f"    {field}: '{change['old_value']}' → '{change['new_value']}'")

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Analyze data changes in existing symbols with data quality validation')
    parser.add_argument('--yesterday', required=True, help='Yesterday date (YYYYMMDD)')
    parser.add_argument('--today', required=True, help='Today date (YYYYMMDD)')
    parser.add_argument('--data-dir', default='../master_symbology/data', help='Data directory')
    parser.add_argument('--ca-dir', default='../corporate_actions/data', help='Corporate actions directory')

    args = parser.parse_args()

    print(f"DATA CHANGES ANALYSIS: {args.yesterday} -> {args.today}")
    print("=" * 60)

    # First, check data quality
    print("STEP 1: Checking corporate actions data quality...")
    quality_issues = quick_data_quality_check(args.ca_dir, args.today)
    for issue in quality_issues:
        print(f"  {issue}")

    critical_issues = [issue for issue in quality_issues if "❌" in issue or "ERROR" in issue]
    if critical_issues:
        print("\n🚨 CRITICAL DATA QUALITY ISSUES DETECTED!")
        print("   Results may be unreliable. Consider fixing data sources first.")

    print(f"\nSTEP 2: Loading master symbology files...")

    # Load files
    yesterday_file = f"{args.data_dir}/{args.yesterday}_MASTER.csv"
    today_file = f"{args.data_dir}/{args.today}_MASTER.csv"

    old_df = load_master_file(yesterday_file)
    new_df = load_master_file(today_file)

    if old_df is None or new_df is None:
        print("❌ Error loading master files - cannot continue")
        return 1

    print(f"  ✅ {args.yesterday}: {len(old_df):,} records")
    print(f"  ✅ {args.today}: {len(new_df):,} records")

    print(f"\nSTEP 3: Loading corporate actions...")
    # Load corporate actions
    corporate_actions = load_corporate_actions(args.ca_dir, args.today)

    for action_type, df in corporate_actions.items():
        print(f"  {action_type}: {len(df)} records for {args.today}")

    print(f"\nSTEP 4: Analyzing data changes in existing symbols...")
    # Analyze
    results = analyze_data_changes(old_df, new_df, corporate_actions, quality_issues)

    # Save results
    output_file = f"data_changes_analysis_{args.today}.csv"
    results_df = pd.DataFrame([{k: v for k, v in r.items() if k != 'details'} for r in results])
    results_df.to_csv(output_file, index=False)
    print(f"\nResults saved to: {output_file}")

    # Enhanced summary with data quality context
    explained = sum(1 for r in results if r['confidence'] > 0.8)
    needs_investigation = len(results) - explained
    data_quality_concerns = sum(1 for r in results if r['data_quality_concern'])
    significant_changes = sum(1 for r in results if r['significant_changes'])

    print(f"\nSUMMARY:")
    print(f"  Total symbols with data changes: {len(results)}")
    print(f"  ✅ Explained by corporate actions: {explained}")
    print(f"  🚨 Need investigation: {needs_investigation}")
    print(f"  🔥 Significant changes (CUSIP, name, etc.): {significant_changes}")
    if data_quality_concerns > 0:
        print(f"  ⚠️  Potentially affected by data quality issues: {data_quality_concerns}")

    if critical_issues:
        print(f"\n⚠️  WARNING: {len(critical_issues)} critical data quality issues detected.")
        print("   Some unexplained changes may be due to missing/corrupt corporate actions data.")

    return 0


if __name__ == "__main__":
    exit(main())