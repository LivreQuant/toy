#!/usr/bin/env python3
"""
Corporate Actions Validation Script

This script validates new and missing entries from master symbology files
against corporate actions data to identify explainable changes vs unexplained ones
that require manual investigation.
"""

import os
import pandas as pd
import logging
import json
import glob
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass
from config import config


@dataclass
class ValidationResult:
    """Structure to hold validation results for entries"""
    symbol: str
    composite_key: str
    change_type: str  # NEW_ENTRY or MISSING_ENTRY
    explanation: str
    explained: bool
    corporate_action_type: str = None
    corporate_action_date: str = None
    confidence: float = 0.0
    details: Dict = None


class CorporateActionsValidator:
    """Validates new/missing entries against corporate actions data"""

    def __init__(self):
        """Initialize the validator using config"""
        # Setup logging
        self.setup_logging()

        # Load data from config
        self.new_entries_df = self.load_csv_file(config.NEW_ENTRIES_FILE)
        self.missing_entries_df = self.load_csv_file(config.MISSING_ENTRIES_FILE)

        # Corporate actions unified data containers
        self.symbol_changes_df = pd.DataFrame()
        self.mergers_df = pd.DataFrame()
        self.spinoffs_df = pd.DataFrame()
        self.delistings_df = pd.DataFrame()
        self.ipos_df = pd.DataFrame()

        # Load unified corporate actions
        self.load_unified_corporate_actions()

        # Validation results
        self.validation_results: List[ValidationResult] = []

    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = Path(config.OUTPUT_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f"validation_{datetime.now().strftime('%Y%m%d')}.log"

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(log_file)
            ]
        )
        self.logger = logging.getLogger(__name__)

    def load_csv_file(self, file_path: str) -> pd.DataFrame:
        """Load CSV file and return DataFrame"""
        if not os.path.exists(file_path):
            self.logger.warning(f"File not found: {file_path}")
            return pd.DataFrame()

        try:
            df = pd.read_csv(file_path)
            self.logger.info(f"Loaded {len(df)} records from {file_path}")
            return df
        except Exception as e:
            self.logger.error(f"Error loading {file_path}: {e}")
            return pd.DataFrame()

    def load_unified_corporate_actions(self):
        """Load unified corporate actions data"""
        self.logger.info("Loading unified corporate actions data...")

        # Get current date directory
        ymd = datetime.strftime(datetime.today(), "%Y%m%d")
        ca_data_dir = os.path.join(config.CORPORATE_ACTIONS_DIR, ymd, "data")

        if not os.path.exists(ca_data_dir):
            self.logger.error(f"Corporate actions data directory not found: {ca_data_dir}")
            return

        # Load unified CSV files
        unified_files = {
            'symbol_changes': 'unified_symbol_changes.csv',
            'mergers': 'unified_mergers.csv',
            'spinoffs': 'unified_spinoffs.csv',
            'delistings': 'unified_delisting.csv',
            'ipos': 'unified_ipos.csv'
        }

        for action_type, filename in unified_files.items():
            file_path = os.path.join(ca_data_dir, filename)
            if os.path.exists(file_path):
                try:
                    df = pd.read_csv(file_path)
                    setattr(self, f"{action_type}_df", df)
                    self.logger.info(f"Loaded {len(df)} {action_type} records from {filename}")
                except Exception as e:
                    self.logger.error(f"Error loading {filename}: {e}")
            else:
                self.logger.warning(f"Unified file not found: {file_path}")

    def validate_new_entries(self) -> List[ValidationResult]:
        """Validate new entries against corporate actions"""
        results = []

        self.logger.info(f"Validating {len(self.new_entries_df)} new entries...")

        for _, row in self.new_entries_df.iterrows():
            symbol = row.get('symbol', '')
            composite_key = row.get('composite_key', '')

            # Check for symbol changes (new symbol appearing)
            symbol_change_explanation = self.check_for_symbol_change_new(symbol, row)
            if symbol_change_explanation:
                results.append(symbol_change_explanation)
                continue

            # Check for IPOs
            ipo_explanation = self.check_for_ipo(symbol, row)
            if ipo_explanation:
                results.append(ipo_explanation)
                continue

            # Check for spinoffs (new symbol from spinoff)
            spinoff_explanation = self.check_for_spinoff_new(symbol, row)
            if spinoff_explanation:
                results.append(spinoff_explanation)
                continue

            # If no explanation found
            results.append(ValidationResult(
                symbol=symbol,
                composite_key=composite_key,
                change_type='NEW_ENTRY',
                explanation='No corporate action found to explain new entry',
                explained=False,
                confidence=0.0
            ))

        return results

    def validate_missing_entries(self) -> List[ValidationResult]:
        """Validate missing entries against corporate actions"""
        results = []

        self.logger.info(f"Validating {len(self.missing_entries_df)} missing entries...")

        for _, row in self.missing_entries_df.iterrows():
            symbol = row.get('symbol', '')
            composite_key = row.get('composite_key', '')

            # Check for symbol changes (old symbol disappearing)
            symbol_change_explanation = self.check_for_symbol_change_missing(symbol, row)
            if symbol_change_explanation:
                results.append(symbol_change_explanation)
                continue

            # Check for delistings
            delisting_explanation = self.check_for_delisting(symbol, row)
            if delisting_explanation:
                results.append(delisting_explanation)
                continue

            # Check for mergers (target company)
            merger_explanation = self.check_for_merger_missing(symbol, row)
            if merger_explanation:
                results.append(merger_explanation)
                continue

            # If no explanation found
            results.append(ValidationResult(
                symbol=symbol,
                composite_key=composite_key,
                change_type='MISSING_ENTRY',
                explanation='No corporate action found to explain missing entry',
                explained=False,
                confidence=0.0
            ))

        return results

    def check_for_ipo(self, symbol: str, row: pd.Series) -> ValidationResult:
        """Check if new entry can be explained by an IPO"""
        if not self.ipos_df.empty:
            ipo_matches = self.ipos_df[self.ipos_df['master_symbol'] == symbol]

            if not ipo_matches.empty:
                ipo_action = ipo_matches.iloc[0]
                return ValidationResult(
                    symbol=symbol,
                    composite_key=row.get('composite_key', ''),
                    change_type='NEW_ENTRY',
                    explanation=f'IPO detected: {symbol} went public',
                    explained=True,
                    corporate_action_type='IPO',
                    corporate_action_date=ipo_action.get('list_date', ''),
                    confidence=ipo_action.get('overall_confidence', 0.8),
                    details={'source': ipo_action.get('source'), 'ipo_data': ipo_action.to_dict()}
                )

        return None

    def check_for_symbol_change_new(self, symbol: str, row: pd.Series) -> ValidationResult:
        """Check if new entry can be explained by a symbol change"""
        if not self.symbol_changes_df.empty:
            # Look for symbol changes where this is the new symbol
            symbol_changes = self.symbol_changes_df[self.symbol_changes_df['new_symbol'] == symbol]

            if not symbol_changes.empty:
                change_action = symbol_changes.iloc[0]
                return ValidationResult(
                    symbol=symbol,
                    composite_key=row.get('composite_key', ''),
                    change_type='NEW_ENTRY',
                    explanation=f'Symbol change detected: {change_action.get("old_symbol", "unknown")} changed to {symbol}',
                    explained=True,
                    corporate_action_type='SYMBOL_CHANGE',
                    corporate_action_date=change_action.get('change_date', ''),
                    confidence=change_action.get('overall_confidence', 0.9),
                    details={'source': change_action.get('source'), 'old_symbol': change_action.get('old_symbol'),
                             'action_data': change_action.to_dict()}
                )

        return None

    def check_for_spinoff_new(self, symbol: str, row: pd.Series) -> ValidationResult:
        """Check if new entry can be explained by a spinoff"""
        if not self.spinoffs_df.empty:
            # Look for spinoffs where this symbol is the spun-off company
            spinoff_matches = self.spinoffs_df[self.spinoffs_df['spinoff_symbol'] == symbol]

            if not spinoff_matches.empty:
                spinoff_action = spinoff_matches.iloc[0]
                return ValidationResult(
                    symbol=symbol,
                    composite_key=row.get('composite_key', ''),
                    change_type='NEW_ENTRY',
                    explanation=f'Spinoff detected: {symbol} spun off from {spinoff_action.get("master_symbol", "unknown")}',
                    explained=True,
                    corporate_action_type='SPINOFF',
                    corporate_action_date=spinoff_action.get('ex_date', ''),
                    confidence=spinoff_action.get('overall_confidence', 0.85),
                    details={'source': spinoff_action.get('source'),
                             'parent_company': spinoff_action.get('master_symbol'),
                             'action_data': spinoff_action.to_dict()}
                )

        return None

    def check_for_delisting(self, symbol: str, row: pd.Series) -> ValidationResult:
        """Check if missing entry can be explained by a delisting"""
        if not self.delistings_df.empty:
            delisting_matches = self.delistings_df[self.delistings_df['master_symbol'] == symbol]

            if not delisting_matches.empty:
                delisting_action = delisting_matches.iloc[0]
                return ValidationResult(
                    symbol=symbol,
                    composite_key=row.get('composite_key', ''),
                    change_type='MISSING_ENTRY',
                    explanation=f'Delisting detected: {symbol} - {delisting_action.get("delisting_reason", "delisted")}',
                    explained=True,
                    corporate_action_type='DELISTING',
                    corporate_action_date=delisting_action.get('delisting_date', ''),
                    confidence=delisting_action.get('overall_confidence', 0.9),
                    details={'source': delisting_action.get('source'),
                             'delisting_reason': delisting_action.get('delisting_reason'),
                             'action_data': delisting_action.to_dict()}
                )

        return None

    def check_for_merger_missing(self, symbol: str, row: pd.Series) -> ValidationResult:
        """Check if missing entry can be explained by a merger (target company)"""
        if not self.mergers_df.empty:
            # Look for mergers where this symbol is the target (acquiree)
            merger_matches = self.mergers_df[self.mergers_df['acquiree_symbol'] == symbol]

            if not merger_matches.empty:
                merger_action = merger_matches.iloc[0]
                return ValidationResult(
                    symbol=symbol,
                    composite_key=row.get('composite_key', ''),
                    change_type='MISSING_ENTRY',
                    explanation=f'Merger detected: {symbol} was acquired by {merger_action.get("acquirer_symbol", "unknown")}',
                    explained=True,
                    corporate_action_type='MERGER',
                    corporate_action_date=merger_action.get('ex_date', ''),
                    confidence=merger_action.get('overall_confidence', 0.9),
                    details={'source': merger_action.get('source'), 'acquirer': merger_action.get('acquirer_symbol'),
                             'action_data': merger_action.to_dict()}
                )

        return None

    def check_for_symbol_change_missing(self, symbol: str, row: pd.Series) -> ValidationResult:
        """Check if missing entry can be explained by a symbol change"""
        if not self.symbol_changes_df.empty:
            # Look for symbol changes where this is the old symbol
            symbol_changes = self.symbol_changes_df[self.symbol_changes_df['old_symbol'] == symbol]

            if not symbol_changes.empty:
                change_action = symbol_changes.iloc[0]
                return ValidationResult(
                    symbol=symbol,
                    composite_key=row.get('composite_key', ''),
                    change_type='MISSING_ENTRY',
                    explanation=f'Symbol change detected: {symbol} changed to {change_action.get("new_symbol", "unknown")}',
                    explained=True,
                    corporate_action_type='SYMBOL_CHANGE',
                    corporate_action_date=change_action.get('change_date', ''),
                    confidence=change_action.get('overall_confidence', 0.9),
                    details={'source': change_action.get('source'), 'new_symbol': change_action.get('new_symbol'),
                             'action_data': change_action.to_dict()}
                )

        return None

    def run_validation(self) -> Tuple[List[ValidationResult], List[ValidationResult]]:
        """Run complete validation process"""
        self.logger.info("Starting corporate actions validation...")

        # Validate new entries
        new_results = self.validate_new_entries()

        # Validate missing entries
        missing_results = self.validate_missing_entries()

        # Store results
        self.validation_results = new_results + missing_results

        return new_results, missing_results

    def export_results(self):
        """Export validation results to CSV files"""
        output_path = Path(config.OUTPUT_DIR)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d')

        # Split results by explained/unexplained
        explained_results = [r for r in self.validation_results if r.explained]
        unexplained_results = [r for r in self.validation_results if not r.explained]

        # Export explained results
        if explained_results:
            explained_df = pd.DataFrame([
                {
                    'symbol': r.symbol,
                    'composite_key': r.composite_key,
                    'change_type': r.change_type,
                    'explanation': r.explanation,
                    'corporate_action_type': r.corporate_action_type,
                    'corporate_action_date': r.corporate_action_date,
                    'confidence': r.confidence,
                    'details': str(r.details) if r.details else ''
                }
                for r in explained_results
            ])

            explained_file = output_path / f"explained_changes_{timestamp}.csv"
            explained_df.to_csv(explained_file, index=False)
            self.logger.info(f"Exported {len(explained_results)} explained changes to {explained_file}")

        # Export unexplained results (manual review needed)
        if unexplained_results:
            unexplained_df = pd.DataFrame([
                {
                    'symbol': r.symbol,
                    'composite_key': r.composite_key,
                    'change_type': r.change_type,
                    'explanation': r.explanation,
                    'requires_manual_review': True
                }
                for r in unexplained_results
            ])

            unexplained_file = output_path / f"manual_review_required_{timestamp}.csv"
            unexplained_df.to_csv(unexplained_file, index=False)
            self.logger.info(f"Exported {len(unexplained_results)} unexplained changes to {unexplained_file}")

        # Export summary
        summary_data = {
            'total_entries_analyzed': len(self.validation_results),
            'explained_entries': len(explained_results),
            'unexplained_entries': len(unexplained_results),
            'explanation_rate': len(explained_results) / len(
                self.validation_results) * 100 if self.validation_results else 0,
            'new_entries_total': len([r for r in self.validation_results if r.change_type == 'NEW_ENTRY']),
            'new_entries_explained': len([r for r in explained_results if r.change_type == 'NEW_ENTRY']),
            'missing_entries_total': len([r for r in self.validation_results if r.change_type == 'MISSING_ENTRY']),
            'missing_entries_explained': len([r for r in explained_results if r.change_type == 'MISSING_ENTRY']),
            'timestamp': timestamp
        }

        summary_file = output_path / f"validation_summary_{timestamp}.json"
        with open(summary_file, 'w') as f:
            json.dump(summary_data, f, indent=2)

        self.logger.info(f"Exported summary to {summary_file}")

        return {
            'explained_file': explained_file if explained_results else None,
            'unexplained_file': unexplained_file if unexplained_results else None,
            'summary_file': summary_file
        }

    def print_summary(self):
        """Print validation summary to console"""
        if not self.validation_results:
            print("No validation results to summarize.")
            return

        explained = [r for r in self.validation_results if r.explained]
        unexplained = [r for r in self.validation_results if not r.explained]

        print("\n" + "=" * 80)
        print("CORPORATE ACTIONS VALIDATION SUMMARY")
        print("=" * 80)
        print(f"Total entries analyzed: {len(self.validation_results)}")
        print(
            f"Explained by corporate actions: {len(explained)} ({len(explained) / len(self.validation_results) * 100:.1f}%)")
        print(
            f"Require manual review: {len(unexplained)} ({len(unexplained) / len(self.validation_results) * 100:.1f}%)")
        print()

        # Breakdown by change type
        new_entries = [r for r in self.validation_results if r.change_type == 'NEW_ENTRY']
        missing_entries = [r for r in self.validation_results if r.change_type == 'MISSING_ENTRY']

        print("NEW ENTRIES:")
        new_explained = [r for r in new_entries if r.explained]
        print(f"  Total: {len(new_entries)}")
        print(
            f"  Explained: {len(new_explained)} ({len(new_explained) / len(new_entries) * 100 if new_entries else 0:.1f}%)")
        print(f"  Manual review needed: {len(new_entries) - len(new_explained)}")

        print("\nMISSING ENTRIES:")
        missing_explained = [r for r in missing_entries if r.explained]
        print(f"  Total: {len(missing_entries)}")
        print(
            f"  Explained: {len(missing_explained)} ({len(missing_explained) / len(missing_entries) * 100 if missing_entries else 0:.1f}%)")
        print(f"  Manual review needed: {len(missing_entries) - len(missing_explained)}")

        # Corporate action type breakdown
        if explained:
            print("\nCORPORATE ACTION TYPES FOUND:")
            action_counts = {}
            for result in explained:
                action_type = result.corporate_action_type or 'Unknown'
                action_counts[action_type] = action_counts.get(action_type, 0) + 1

            for action_type, count in sorted(action_counts.items()):
                print(f"  {action_type}: {count}")

        if unexplained:
            print(f"\n{len(unexplained)} entries require manual investigation")
            print("Check the manual_review_required_*.csv file for details")

        print("=" * 80 + "\n")


def main():
    """Main execution function"""
    # Initialize validator using config
    validator = CorporateActionsValidator()

    # Run validation
    try:
        new_results, missing_results = validator.run_validation()

        # Print summary
        validator.print_summary()

        # Export results
        output_files = validator.export_results()

        print("OUTPUT FILES:")
        for file_type, file_path in output_files.items():
            if file_path:
                print(f"  {file_type}: {file_path}")

        return 0

    except Exception as e:
        logging.error(f"Validation failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())