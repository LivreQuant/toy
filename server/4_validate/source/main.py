#!/usr/bin/env python3
"""
Enhanced Corporate Actions Validation Script with Portfolio Impact Detection
"""

import logging
import sys
from typing import List
from corporate_actions_validator import CorporateActionsValidator
from summary_reporter import SummaryReporter


def main():
    """Main execution function"""
    try:
        # Your portfolio symbols
        portfolio_symbols = [
            'XIN', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA',
            'JNJ', 'JPM', 'V', 'PG', 'UNH', 'HD', 'MA', 'DIS', 'NFLX'
        ]

        print("Starting Enhanced Corporate Actions Validation...")
        print(f"Monitoring {len(portfolio_symbols)} portfolio symbols")

        # Initialize validator
        validator = CorporateActionsValidator(portfolio_symbols)

        # Run validation
        new_results, missing_results = validator.run_validation()

        # Generate reports using updated exporter
        reporter = SummaryReporter(validator.validation_results)
        exporter = validator.get_results_exporter()  # Gets exporter with original files

        # Print summary
        reporter.print_summary()

        # Export results with audit trail
        output_files = exporter.export_results()

        print("\nOUTPUT FILES:")
        file_descriptions = {
            'explained_file': 'Truly Explained (passed legitimacy)',
            'ultra_high_priority_file': 'ULTRA HIGH Priority Manual Review',
            'high_priority_file': 'HIGH Priority Manual Review',
            'medium_priority_file': 'MEDIUM Priority Manual Review',
            'low_priority_file': 'LOW Priority Manual Review',
            'audit_new_entries': 'Audit Trail - New Entries (proves all processed)',
            'audit_missing_entries': 'Audit Trail - Missing Entries (proves all processed)',
            'summary_file': 'Validation Summary'
        }

        for file_type, file_path in output_files.items():
            if file_path:
                description = file_descriptions.get(file_type, file_type)
                print(f"  {description}: {file_path}")

        # Check for issues
        failed_legitimacy = len([r for r in validator.validation_results if r.explained and not r.legitimacy_passed])
        ultra_high = len([r for r in validator.validation_results if r.priority_for_review == "ULTRA_HIGH"])

        if failed_legitimacy > 0:
            print(f"\n🚨 LEGITIMACY FAILURES: {failed_legitimacy} corporate actions failed verification!")
            print("These need immediate investigation - something is suspicious")

        if ultra_high > 0:
            print(f"\n⚠️ ULTRA HIGH PRIORITY: {ultra_high} items need immediate attention")

        return 2 if (failed_legitimacy > 0 or ultra_high > 0) else 0

    except Exception as e:
        logging.error(f"Validation failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())