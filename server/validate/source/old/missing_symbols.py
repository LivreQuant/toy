#!/usr/bin/env python3
"""
Disappeared Symbols Analyzer - Analyzes symbols that were in yesterday's file but not today's
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

    # Load delistings
    try:
        delistings = pd.read_csv(f"{ca_dir}/delistings.csv")
        delistings['delisting_date'] = pd.to_datetime(delistings['delisting_date'], errors='coerce')
        target_date = pd.to_datetime(date_str)
        delistings = delistings[delistings['delisting_date'] == target_date]
        corporate_actions['delistings'] = delistings
    except:
        corporate_actions['delistings'] = pd.DataFrame()

    # Load mergers
    try:
        mergers = pd.read_csv(f"{ca_dir}/mergers.csv")
        mergers['ex_date'] = pd.to_datetime(mergers['ex_date'], errors='coerce')
        target_date = pd.to_datetime(date_str)
        mergers = mergers[mergers['ex_date'] == target_date]
        corporate_actions['mergers'] = mergers
    except:
        corporate_actions['mergers'] = pd.DataFrame()

    # Load symbol changes
    try:
        symbol_changes = pd.read_csv(f"{ca_dir}/symbol_changes.csv")
        symbol_changes['change_date'] = pd.to_datetime(symbol_changes['change_date'], errors='coerce')
        target_date = pd.to_datetime(date_str)
        symbol_changes = symbol_changes[symbol_changes['change_date'] == target_date]
        corporate_actions['symbol_changes'] = symbol_changes
    except:
        corporate_actions['symbol_changes'] = pd.DataFrame()

    # Load rights (for expiring rights)
    try:
        rights = pd.read_csv(f"{ca_dir}/rights.csv")
        # For rights expiry, we might need to check a different date field
        # For now, using ex_date as proxy
        rights['ex_date'] = pd.to_datetime(rights['ex_date'], errors='coerce')
        target_date = pd.to_datetime(date_str)
        rights = rights[rights['ex_date'] == target_date]
        corporate_actions['rights'] = rights
    except:
        corporate_actions['rights'] = pd.DataFrame()

    return corporate_actions


def analyze_disappeared_symbols(old_df, new_df, corporate_actions, data_quality_issues):
    """Find disappeared symbols and try to explain them"""

    # Create composite keys (symbol:exchange)
    old_keys = set(old_df['symbol'] + ':' + old_df['exchange'])
    new_keys = set(new_df['symbol'] + ':' + new_df['exchange'])

    # Find disappeared symbols
    disappeared_keys = old_keys - new_keys
    disappeared_df = old_df[
        (old_df['symbol'] + ':' + old_df['exchange']).isin(disappeared_keys)
    ].copy()

    results = []

    print(f"Found {len(disappeared_df)} disappeared symbols")
    print("-" * 50)

    # Check if we have critical data issues that might affect results
    critical_issues = [issue for issue in data_quality_issues if "❌" in issue or "ERROR" in issue]
    missing_data_warnings = [issue for issue in data_quality_issues if "NO DATA FOR" in issue]

    for _, row in disappeared_df.iterrows():
        symbol = row['symbol']
        exchange = row['exchange']
        name = row.get('name', '')

        # Try to explain why this symbol disappeared
        explanation = "UNEXPLAINED - Requires investigation"
        confidence = 0.0
        data_quality_concern = False

        # Check delistings
        delisting_match = corporate_actions['delistings'][
            corporate_actions['delistings']['delisted_symbol'] == symbol
            ]
        if not delisting_match.empty:
            reason = delisting_match.iloc[0].get('delisting_reason', 'Unknown')
            delisting_type = delisting_match.iloc[0].get('delisting_type', '')
            explanation = f"DELISTED: {reason}"
            if delisting_type:
                explanation += f" ({delisting_type})"
            confidence = 0.95

        # Check mergers (company being acquired)
        elif not corporate_actions['mergers'].empty:
            merger_match = corporate_actions['mergers'][
                corporate_actions['mergers']['acquiree_symbol'] == symbol
                ]
            if not merger_match.empty:
                acquirer = merger_match.iloc[0].get('acquirer_symbol', '')
                deal_type = merger_match.iloc[0].get('deal_type', 'merger')
                explanation = f"ACQUIRED by {acquirer} ({deal_type})"
                confidence = 0.90

        # Check symbol changes (old symbol changed)
        elif not corporate_actions['symbol_changes'].empty:
            symbol_change_match = corporate_actions['symbol_changes'][
                corporate_actions['symbol_changes']['old_symbol'] == symbol
                ]
            if not symbol_change_match.empty:
                new_symbol = symbol_change_match.iloc[0].get('new_symbol', '')
                explanation = f"SYMBOL CHANGED to {new_symbol}"
                confidence = 0.95

        # Check rights expiry (for rights symbols)
        elif '.RT' in symbol or 'RT' in symbol or symbol.endswith('R'):
            base_symbol = symbol.replace('.RT', '').replace('RT', '').rstrip('R')
            rights_match = corporate_actions['rights'][
                corporate_actions['rights']['issuing_symbol'] == base_symbol
                ]
            if not rights_match.empty:
                explanation = f"RIGHTS EXPIRED for {base_symbol}"
                confidence = 0.85
            else:
                explanation = "POSSIBLE RIGHTS EXPIRY (not confirmed in corporate actions)"
                confidence = 0.40
                data_quality_concern = True

        # If unexplained, check if it might be due to data quality issues
        if confidence == 0.0:
            potential_causes = []

            if any("delistings.csv" in issue for issue in critical_issues):
                potential_causes.append("delisting data missing/corrupt")
                data_quality_concern = True
            elif any("NO DATA FOR" in issue and "delistings.csv" in issue for issue in missing_data_warnings):
                potential_causes.append("no delisting data for this date")
                data_quality_concern = True

            if any("mergers.csv" in issue for issue in critical_issues):
                potential_causes.append("merger data missing/corrupt")
                data_quality_concern = True
            elif any("NO DATA FOR" in issue and "mergers.csv" in issue for issue in missing_data_warnings):
                potential_causes.append("no merger data for this date")
                data_quality_concern = True

            if potential_causes:
                explanation += f" ({'; '.join(potential_causes)})"

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
    parser = argparse.ArgumentParser(description='Analyze disappeared symbols with data quality validation')
    parser.add_argument('--yesterday', required=True, help='Yesterday date (YYYYMMDD)')
    parser.add_argument('--today', required=True, help='Today date (YYYYMMDD)')
    parser.add_argument('--data-dir', default='../master_symbology/data', help='Data directory')
    parser.add_argument('--ca-dir', default='../corporate_actions/data', help='Corporate actions directory')

    args = parser.parse_args()

    print(f"DISAPPEARED SYMBOLS ANALYSIS: {args.yesterday} -> {args.today}")
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

    print(f"\nSTEP 4: Analyzing disappeared symbols...")
    # Analyze
    results = analyze_disappeared_symbols(old_df, new_df, corporate_actions, quality_issues)

    # Save results
    output_file = f"disappeared_symbols_analysis_{args.today}.csv"
    pd.DataFrame(results).to_csv(output_file, index=False)
    print(f"\nResults saved to: {output_file}")

    # Enhanced summary with data quality context
    explained = sum(1 for r in results if r['confidence'] > 0.8)
    needs_investigation = len(results) - explained
    data_quality_concerns = sum(1 for r in results if r['data_quality_concern'])

    print(f"\nSUMMARY:")
    print(f"  Total disappeared symbols: {len(results)}")
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