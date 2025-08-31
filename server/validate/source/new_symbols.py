#!/usr/bin/env python3
"""
New Symbols Analyzer - Analyzes symbols that appear in today's file but not yesterday's
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

    # Load IPOs
    try:
        ipos = pd.read_csv(f"{ca_dir}/ipos.csv")
        ipos['listing_date'] = pd.to_datetime(ipos['listing_date'], errors='coerce')
        target_date = pd.to_datetime(date_str)
        ipos = ipos[ipos['listing_date'] == target_date]
        corporate_actions['ipos'] = ipos
    except:
        corporate_actions['ipos'] = pd.DataFrame()

    # Load spinoffs
    try:
        spinoffs = pd.read_csv(f"{ca_dir}/spinoffs.csv")
        spinoffs['ex_date'] = pd.to_datetime(spinoffs['ex_date'], errors='coerce')
        target_date = pd.to_datetime(date_str)
        spinoffs = spinoffs[spinoffs['ex_date'] == target_date]
        corporate_actions['spinoffs'] = spinoffs
    except:
        corporate_actions['spinoffs'] = pd.DataFrame()

    # Load symbol changes
    try:
        symbol_changes = pd.read_csv(f"{ca_dir}/symbol_changes.csv")
        symbol_changes['change_date'] = pd.to_datetime(symbol_changes['change_date'], errors='coerce')
        target_date = pd.to_datetime(date_str)
        symbol_changes = symbol_changes[symbol_changes['change_date'] == target_date]
        corporate_actions['symbol_changes'] = symbol_changes
    except:
        corporate_actions['symbol_changes'] = pd.DataFrame()

    # Load rights offerings
    try:
        rights = pd.read_csv(f"{ca_dir}/rights.csv")
        rights['ex_date'] = pd.to_datetime(rights['ex_date'], errors='coerce')
        target_date = pd.to_datetime(date_str)
        rights = rights[rights['ex_date'] == target_date]
        corporate_actions['rights'] = rights
    except:
        corporate_actions['rights'] = pd.DataFrame()

    return corporate_actions


def analyze_new_symbols(old_df, new_df, corporate_actions, data_quality_issues):
    """Find new symbols and try to explain them"""

    # Create composite keys (symbol:exchange)
    old_keys = set(old_df['symbol'] + ':' + old_df['exchange'])
    new_keys = set(new_df['symbol'] + ':' + new_df['exchange'])

    # Find new symbols
    new_symbol_keys = new_keys - old_keys
    new_symbols_df = new_df[
        (new_df['symbol'] + ':' + new_df['exchange']).isin(new_symbol_keys)
    ].copy()

    results = []

    print(f"Found {len(new_symbols_df)} new symbols")
    print("-" * 50)

    # Check if we have critical data issues that might affect results
    critical_issues = [issue for issue in data_quality_issues if "❌" in issue or "ERROR" in issue]
    missing_data_warnings = [issue for issue in data_quality_issues if "NO DATA FOR" in issue]

    for _, row in new_symbols_df.iterrows():
        symbol = row['symbol']
        exchange = row['exchange']
        name = row.get('name', '')

        # Try to explain this new symbol
        explanation = "UNEXPLAINED - Requires investigation"
        confidence = 0.0
        data_quality_concern = False

        # Check IPOs
        ipo_match = corporate_actions['ipos'][
            corporate_actions['ipos']['ipo_symbol'] == symbol
            ]
        if not ipo_match.empty:
            explanation = f"NEW IPO: {ipo_match.iloc[0].get('company_name', '')}"
            confidence = 0.95

        # Check spinoffs
        elif not corporate_actions['spinoffs'].empty:
            spinoff_match = corporate_actions['spinoffs'][
                corporate_actions['spinoffs']['new_symbol'] == symbol
                ]
            if not spinoff_match.empty:
                parent = spinoff_match.iloc[0].get('master_symbol', '')
                explanation = f"SPINOFF from {parent}"
                confidence = 0.90

        # Check symbol changes (new symbol)
        elif not corporate_actions['symbol_changes'].empty:
            symbol_change_match = corporate_actions['symbol_changes'][
                corporate_actions['symbol_changes']['new_symbol'] == symbol
                ]
            if not symbol_change_match.empty:
                old_symbol = symbol_change_match.iloc[0].get('old_symbol', '')
                explanation = f"SYMBOL CHANGE from {old_symbol}"
                confidence = 0.95

        # Check rights offerings (might create temporary symbols)
        elif not corporate_actions['rights'].empty:
            # Rights symbols often have .RT suffix or similar patterns
            base_symbol = symbol.replace('.RT', '').replace('RT', '').rstrip('R')
            rights_match = corporate_actions['rights'][
                corporate_actions['rights']['issuing_symbol'] == base_symbol
                ]
            if not rights_match.empty:
                explanation = f"RIGHTS OFFERING for {base_symbol}"
                confidence = 0.80

        # If unexplained, check if it might be due to data quality issues
        if confidence == 0.0:
            if any("ipos.csv" in issue for issue in critical_issues):
                explanation += " (IPO data missing/corrupt)"
                data_quality_concern = True
            elif any("NO DATA FOR" in issue and "ipos.csv" in issue for issue in missing_data_warnings):
                explanation += " (no IPO data for this date)"
                data_quality_concern = True

        result = {
            'symbol': symbol,
            'exchange': exchange,
            'name': name,
            'explanation': explanation,
            'confidence': confidence,
            'data_quality_concern': data_quality_concern
        }
        results.append(result)

        status = "✅" if confidence > 0.8 else "❓" if confidence > 0.5 else "🚨"
        concern_flag = " ⚠️" if data_quality_concern else ""
        print(f"{status} {symbol}:{exchange} - {explanation}{concern_flag}")

    return results


def main():
    parser = argparse.ArgumentParser(description='Analyze new symbols with data quality validation')
    parser.add_argument('--yesterday', required=True, help='Yesterday date (YYYYMMDD)')
    parser.add_argument('--today', required=True, help='Today date (YYYYMMDD)')
    parser.add_argument('--data-dir', default='../master_symbology/data', help='Data directory')
    parser.add_argument('--ca-dir', default='../corporate_actions/data', help='Corporate actions directory')

    args = parser.parse_args()

    print(f"NEW SYMBOLS ANALYSIS: {args.yesterday} -> {args.today}")
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

    print(f"\nSTEP 4: Analyzing new symbols...")
    # Analyze
    results = analyze_new_symbols(old_df, new_df, corporate_actions, quality_issues)

    # Save results
    output_file = f"new_symbols_analysis_{args.today}.csv"
    pd.DataFrame(results).to_csv(output_file, index=False)
    print(f"\nResults saved to: {output_file}")

    # Enhanced summary with data quality context
    explained = sum(1 for r in results if r['confidence'] > 0.8)
    needs_investigation = len(results) - explained
    data_quality_concerns = sum(1 for r in results if r['data_quality_concern'])

    print(f"\nSUMMARY:")
    print(f"  Total new symbols: {len(results)}")
    print(f"  ✅ Explained by corporate actions: {explained}")
    print(f"  🚨 Need investigation: {needs_investigation}")
    if data_quality_concerns > 0:
        print(f"  ⚠️  Potentially affected by data quality issues: {data_quality_concerns}")

    if critical_issues:
        print(f"\n⚠️  WARNING: {len(critical_issues)} critical data quality issues detected.")
        print("   Some unexplained symbols may be due to missing/corrupt corporate actions data.")

    return 0


if __name__ == "__main__":
    exit(main())