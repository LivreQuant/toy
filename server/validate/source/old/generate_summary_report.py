#!/usr/bin/env python3
"""
Generate comprehensive summary report from the 3 analysis files
Includes data quality assessment since we don't trust the data sources
"""

import pandas as pd
import argparse
import os
from datetime import datetime


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
                date_cols = [col for col in df.columns if 'date' in col.lower()]
                if not date_cols:
                    issues.append(f"⚠️  NO DATE COLUMN: {ca_file}")
                else:
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


def generate_summary_report(date_str, ca_dir=None):
    """Generate unified summary from all 3 analysis files"""

    # Load results from the 3 scripts
    try:
        new_symbols = pd.read_csv(f"new_symbols_analysis_{date_str}.csv")
    except:
        new_symbols = pd.DataFrame()
        print("⚠️  Warning: new_symbols_analysis file not found")

    try:
        disappeared = pd.read_csv(f"disappeared_symbols_analysis_{date_str}.csv")
    except:
        disappeared = pd.DataFrame()
        print("⚠️  Warning: disappeared_symbols_analysis file not found")

    try:
        data_changes = pd.read_csv(f"data_changes_analysis_{date_str}.csv")
    except:
        data_changes = pd.DataFrame()
        print("⚠️  Warning: data_changes_analysis file not found")

    # Get data quality assessment if corporate actions directory provided
    quality_issues = []
    if ca_dir:
        quality_issues = quick_data_quality_check(ca_dir, date_str)

    # Generate summary report
    report = []
    report.append(f"MASTER SYMBOLOGY CHANGE SUMMARY - {date_str}")
    report.append("=" * 60)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")

    # Data quality assessment
    if quality_issues:
        report.append("DATA QUALITY ASSESSMENT:")
        critical_issues = [issue for issue in quality_issues if "❌" in issue or "ERROR" in issue]
        missing_data_issues = [issue for issue in quality_issues if "NO DATA FOR" in issue]

        if critical_issues:
            report.append("  🚨 CRITICAL ISSUES:")
            for issue in critical_issues:
                report.append(f"    {issue}")

        if missing_data_issues:
            report.append("  ⚠️  MISSING DATA FOR TARGET DATE:")
            for issue in missing_data_issues:
                report.append(f"    {issue}")

        good_files = [issue for issue in quality_issues if "✅" in issue]
        if good_files:
            report.append("  ✅ GOOD DATA:")
            for issue in good_files[:3]:  # Show first 3 to save space
                report.append(f"    {issue}")
            if len(good_files) > 3:
                report.append(f"    ... and {len(good_files) - 3} more")

        report.append("")

    # New symbols summary
    new_explained = len(new_symbols[new_symbols['confidence'] > 0.8]) if not new_symbols.empty else 0
    new_unexplained = len(new_symbols[new_symbols['confidence'] <= 0.8]) if not new_symbols.empty else 0
    new_data_concerns = len(
        new_symbols[new_symbols.get('data_quality_concern', False) == True]) if not new_symbols.empty else 0

    report.append(f"NEW SYMBOLS: {len(new_symbols)} total")
    report.append(f"  ✅ Explained by corporate actions: {new_explained}")
    report.append(f"  🚨 Need investigation: {new_unexplained}")
    if new_data_concerns > 0:
        report.append(f"  ⚠️  May be affected by data quality issues: {new_data_concerns}")
    report.append("")

    # Disappeared symbols summary
    dis_explained = len(disappeared[disappeared['confidence'] > 0.8]) if not disappeared.empty else 0
    dis_unexplained = len(disappeared[disappeared['confidence'] <= 0.8]) if not disappeared.empty else 0
    dis_data_concerns = len(
        disappeared[disappeared.get('data_quality_concern', False) == True]) if not disappeared.empty else 0

    report.append(f"DISAPPEARED SYMBOLS: {len(disappeared)} total")
    report.append(f"  ✅ Explained by corporate actions: {dis_explained}")
    report.append(f"  🚨 Need investigation: {dis_unexplained}")
    if dis_data_concerns > 0:
        report.append(f"  ⚠️  May be affected by data quality issues: {dis_data_concerns}")
    report.append("")

    # Data changes summary
    data_explained = len(data_changes[data_changes['confidence'] > 0.8]) if not data_changes.empty else 0
    data_unexplained = len(data_changes[data_changes['confidence'] <= 0.8]) if not data_changes.empty else 0
    data_concerns = len(
        data_changes[data_changes.get('data_quality_concern', False) == True]) if not data_changes.empty else 0
    significant_changes = len(
        data_changes[data_changes.get('significant_changes', '') != '']) if not data_changes.empty else 0

    report.append(f"DATA CHANGES: {len(data_changes)} symbols total")
    report.append(f"  ✅ Explained by corporate actions: {data_explained}")
    report.append(f"  🚨 Need investigation: {data_unexplained}")
    report.append(f"  🔥 Significant changes (CUSIP, name, etc.): {significant_changes}")
    if data_concerns > 0:
        report.append(f"  ⚠️  May be affected by data quality issues: {data_concerns}")
    report.append("")

    # Overall assessment
    total_changes = len(new_symbols) + len(disappeared) + len(data_changes)
    total_explained = new_explained + dis_explained + data_explained
    total_unexplained = new_unexplained + dis_unexplained + data_unexplained
    total_data_concerns = new_data_concerns + dis_data_concerns + data_concerns

    report.append("OVERALL ASSESSMENT:")
    report.append(f"  Total changes detected: {total_changes}")
    report.append(
        f"  ✅ Successfully explained: {total_explained} ({total_explained / total_changes * 100:.1f}%)" if total_changes > 0 else "  ✅ Successfully explained: 0 (0.0%)")
    report.append(
        f"  🚨 Require investigation: {total_unexplained} ({total_unexplained / total_changes * 100:.1f}%)" if total_changes > 0 else "  🚨 Require investigation: 0 (0.0%)")

    if total_data_concerns > 0:
        report.append(
            f"  ⚠️  Potentially affected by data quality: {total_data_concerns} ({total_data_concerns / total_changes * 100:.1f}%)")
    report.append("")

    # Critical issues requiring immediate attention
    if total_unexplained > 0 or (quality_issues and any("❌" in issue for issue in quality_issues)):
        report.append("🚨 CRITICAL ISSUES REQUIRING IMMEDIATE ATTENTION:")

        if any("❌" in issue for issue in quality_issues):
            report.append("   DATA QUALITY ISSUES:")
            critical_issues = [issue for issue in quality_issues if "❌" in issue]
            for issue in critical_issues[:5]:  # Show first 5
                report.append(f"     - {issue}")
            if len(critical_issues) > 5:
                report.append(f"     - ... and {len(critical_issues) - 5} more critical issues")

        if total_unexplained > 0:
            report.append("   UNEXPLAINED SYMBOLOGY CHANGES:")

            if new_unexplained > 0:
                report.append(f"     - {new_unexplained} new symbols without corporate actions")
                # Show top 5 examples
                unexplained_new = new_symbols[new_symbols['confidence'] <= 0.8]
                for i, (_, row) in enumerate(unexplained_new.head(5).iterrows()):
                    report.append(f"       • {row['symbol']}:{row['exchange']} ({row.get('name', 'No name')[:30]})")
                if len(unexplained_new) > 5:
                    report.append(f"       • ... and {len(unexplained_new) - 5} more")

            if dis_unexplained > 0:
                report.append(f"     - {dis_unexplained} disappeared symbols without corporate actions")
                unexplained_dis = disappeared[disappeared['confidence'] <= 0.8]
                for i, (_, row) in enumerate(unexplained_dis.head(5).iterrows()):
                    report.append(f"       • {row['symbol']}:{row['exchange']} ({row.get('name', 'No name')[:30]})")
                if len(unexplained_dis) > 5:
                    report.append(f"       • ... and {len(unexplained_dis) - 5} more")

            if data_unexplained > 0:
                report.append(f"     - {data_unexplained} unexplained data changes")
                unexplained_data = data_changes[data_changes['confidence'] <= 0.8]
                for i, (_, row) in enumerate(unexplained_data.head(5).iterrows()):
                    fields = row.get('changed_fields', 'unknown fields')[:50]
                    report.append(f"       • {row['symbol']}:{row['exchange']} ({fields})")
                if len(unexplained_data) > 5:
                    report.append(f"       • ... and {len(unexplained_data) - 5} more")

        report.append("")
    else:
        if total_changes > 0:
            report.append("✅ ALL CHANGES SUCCESSFULLY EXPLAINED!")
            if total_data_concerns > 0:
                report.append("   (Though some may be affected by data quality issues)")
        else:
            report.append("ℹ️  NO SYMBOLOGY CHANGES DETECTED")
        report.append("")

    # Recommendations
    report.append("RECOMMENDED ACTIONS:")
    if any("❌" in issue for issue in quality_issues):
        report.append("  1. 🔧 FIX CRITICAL DATA QUALITY ISSUES FIRST")
        report.append("     - Fix missing/corrupt corporate actions files")
        report.append("     - Verify data source connections and pipelines")

    if total_unexplained > 0:
        report.append("  2. 🔍 INVESTIGATE UNEXPLAINED CHANGES")
        report.append("     - Manually research symbols flagged for investigation")
        report.append("     - Check if corporate actions are missing from data sources")
        report.append("     - Verify with exchange announcements and company press releases")

    if significant_changes > 0:
        report.append("  3. 🔥 REVIEW SIGNIFICANT CHANGES (CUSIP, Name, etc.)")
        report.append("     - Verify CUSIP changes with CUSIP Global Services")
        report.append("     - Cross-check name changes with SEC filings")

    if total_data_concerns > 0:
        report.append("  4. ⚠️  ASSESS DATA QUALITY IMPACT")
        report.append("     - Determine if missing data explains unexplained changes")
        report.append("     - Consider delaying automated decisions until data quality improves")

    # Save and print report
    report_text = '\n'.join(report)

    output_filename = f"symbology_summary_{date_str}.txt"
    with open(output_filename, 'w') as f:
        f.write(report_text)

    print(report_text)
    print(f"\nDETAILED FILES GENERATED:")
    for filename in [f"new_symbols_analysis_{date_str}.csv", f"disappeared_symbols_analysis_{date_str}.csv",
                     f"data_changes_analysis_{date_str}.csv"]:
        if os.path.exists(filename):
            print(f"  ✅ {filename}")
        else:
            print(f"  ❌ {filename} (missing)")
    print(f"  📄 {output_filename}")

    return report_text


def main():
    parser = argparse.ArgumentParser(description='Generate comprehensive summary report with data quality assessment')
    parser.add_argument('--date', required=True, help='Date (YYYYMMDD)')
    parser.add_argument('--ca-dir', help='Corporate actions directory (for data quality check)')

    args = parser.parse_args()

    generate_summary_report(args.date, args.ca_dir)


if __name__ == "__main__":
    main()