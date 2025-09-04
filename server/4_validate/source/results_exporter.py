#!/usr/bin/env python3
"""
Enhanced results exporter with consistent naming and complete entry tracking
"""

import pandas as pd
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List
from config import config
from validation_result import ValidationResult


class ResultsExporter:
    """Enhanced exporter with consistent naming and complete audit trail"""

    def __init__(self, validation_results: List[ValidationResult], new_entries_df: pd.DataFrame,
                 missing_entries_df: pd.DataFrame):
        self.validation_results = validation_results
        self.new_entries_df = new_entries_df.copy()
        self.missing_entries_df = missing_entries_df.copy()
        self.logger = logging.getLogger(__name__)

    def export_results(self) -> dict:
        """Export validation results with consistent naming and complete audit trail"""
        output_path = Path(config.OUTPUT_DIR)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d')

        # Categorize results - FAILED LEGITIMACY IS NOT EXPLAINED!
        truly_explained = [r for r in self.validation_results if r.explained and r.legitimacy_passed]
        failed_legitimacy = [r for r in self.validation_results if r.explained and not r.legitimacy_passed]
        ultra_high_priority = [r for r in self.validation_results if
                               not r.explained and r.priority_for_review == "ULTRA_HIGH"]
        high_priority = [r for r in self.validation_results if not r.explained and r.priority_for_review == "HIGH"]
        medium_priority = [r for r in self.validation_results if not r.explained and r.priority_for_review == "MEDIUM"]
        low_priority = [r for r in self.validation_results if not r.explained and r.priority_for_review == "LOW"]

        # Add failed legitimacy to manual review since they're NOT truly explained
        failed_legitimacy_ultra = [r for r in failed_legitimacy if r.priority_for_review == "ULTRA_HIGH"]
        failed_legitimacy_high = [r for r in failed_legitimacy if r.priority_for_review == "HIGH"]
        failed_legitimacy_medium = [r for r in failed_legitimacy if r.priority_for_review == "MEDIUM"]
        failed_legitimacy_low = [r for r in failed_legitimacy if r.priority_for_review == "LOW"]

        # Combine failed legitimacy with manual review (since they need investigation)
        ultra_high_priority.extend(failed_legitimacy_ultra)
        high_priority.extend(failed_legitimacy_high)
        medium_priority.extend(failed_legitimacy_medium)
        low_priority.extend(failed_legitimacy_low)

        output_files = {}

        # Export truly explained results (ONLY those that passed legitimacy)
        explained_df = self._create_results_dataframe(truly_explained)
        explained_file = output_path / f"explained_{timestamp}.csv"
        explained_df.to_csv(explained_file, sep="|", index=False)
        output_files['explained_file'] = explained_file
        self.logger.info(f"Exported {len(truly_explained)} truly explained changes to {explained_file}")

        # Export manual review files with consistent naming
        if ultra_high_priority:
            ultra_high_df = self._create_results_dataframe(ultra_high_priority)
            ultra_high_file = output_path / f"manual_review_ULTRA_HIGH_PRIORITY_{timestamp}.csv"
            ultra_high_df.to_csv(ultra_high_file, sep="|", index=False)
            output_files['ultra_high_priority_file'] = ultra_high_file
            self.logger.critical(f"Exported {len(ultra_high_priority)} ULTRA HIGH PRIORITY items to {ultra_high_file}")

        if high_priority:
            high_df = self._create_results_dataframe(high_priority)
            high_file = output_path / f"manual_review_HIGH_PRIORITY_{timestamp}.csv"
            high_df.to_csv(high_file, sep="|", index=False)
            output_files['high_priority_file'] = high_file
            self.logger.warning(f"Exported {len(high_priority)} HIGH PRIORITY items to {high_file}")

        if medium_priority:
            medium_df = self._create_results_dataframe(medium_priority)
            medium_file = output_path / f"manual_review_MEDIUM_PRIORITY_{timestamp}.csv"
            medium_df.to_csv(medium_file, sep="|", index=False)
            output_files['medium_priority_file'] = medium_file
            self.logger.info(f"Exported {len(medium_priority)} MEDIUM PRIORITY items to {medium_file}")

        if low_priority:
            low_df = self._create_results_dataframe(low_priority)
            low_file = output_path / f"manual_review_LOW_PRIORITY_{timestamp}.csv"
            low_df.to_csv(low_file, sep="|", index=False)
            output_files['low_priority_file'] = low_file
            self.logger.info(f"Exported {len(low_priority)} LOW PRIORITY items to {low_file}")

        # Create audit trail - annotated original files
        self._create_audit_trail_files(output_path, timestamp, output_files)

        # Export summary
        summary_data = self._create_summary(timestamp, truly_explained, failed_legitimacy,
                                            ultra_high_priority, high_priority, medium_priority, low_priority)

        summary_file = output_path / f"validation_summary_{timestamp}.json"
        with open(summary_file, 'w') as f:
            json.dump(summary_data, f, indent=2)
        output_files['summary_file'] = summary_file

        self.logger.info(f"Exported summary to {summary_file}")

        return output_files

    def _create_audit_trail_files(self, output_path: Path, timestamp: str, output_files: dict):
        """Create annotated versions of original files to prove we processed everything"""

        # Create lookup dictionary for validation results
        result_lookup = {}
        for result in self.validation_results:
            key = f"{result.symbol}_{result.type}_{result.composite_key}"
            result_lookup[key] = result

        # Annotate new entries
        if not self.new_entries_df.empty:
            annotated_new = self._annotate_original_file(self.new_entries_df, result_lookup, "NEW_ENTRY")
            new_audit_file = output_path / f"audit_new_entries_{timestamp}.csv"
            annotated_new.to_csv(new_audit_file, sep="|", index=False)
            output_files['audit_new_entries'] = new_audit_file
            self.logger.info(f"Created audit trail for new entries: {new_audit_file}")

        # Annotate missing entries
        if not self.missing_entries_df.empty:
            annotated_missing = self._annotate_original_file(self.missing_entries_df, result_lookup, "MISSING_ENTRY")
            missing_audit_file = output_path / f"audit_missing_entries_{timestamp}.csv"
            annotated_missing.to_csv(missing_audit_file, sep="|", index=False)
            output_files['audit_missing_entries'] = missing_audit_file
            self.logger.info(f"Created audit trail for missing entries: {missing_audit_file}")

    def _annotate_original_file(self, original_df: pd.DataFrame, result_lookup: dict, change_type: str) -> pd.DataFrame:
        """Add validation status columns to original files"""
        annotated_df = original_df.copy()

        # Add new columns at the beginning
        annotated_df.insert(0, 'validation_status', '')
        annotated_df.insert(1, 'priority_level', '')
        annotated_df.insert(2, 'explanation', '')
        annotated_df.insert(3, 'corporate_action_type', '')
        annotated_df.insert(4, 'legitimacy_passed', '')
        annotated_df.insert(5, 'portfolio_holding', '')

        for index, row in annotated_df.iterrows():
            symbol = row.get('symbol', '')
            type_val = row.get('type', '')
            composite_key = row.get('composite_key', '')

            lookup_key = f"{symbol}_{type_val}_{composite_key}"

            if lookup_key in result_lookup:
                result = result_lookup[lookup_key]

                # Determine validation status
                if result.explained and result.legitimacy_passed:
                    validation_status = "EXPLAINED"
                elif result.explained and not result.legitimacy_passed:
                    validation_status = "MANUAL_REVIEW_LEGITIMACY_FAILED"
                else:
                    validation_status = "MANUAL_REVIEW"

                annotated_df.at[index, 'validation_status'] = validation_status
                annotated_df.at[index, 'priority_level'] = result.priority_for_review
                annotated_df.at[index, 'explanation'] = result.explanation
                annotated_df.at[index, 'corporate_action_type'] = result.corporate_action_type or ''
                annotated_df.at[index, 'legitimacy_passed'] = str(result.legitimacy_passed)
                annotated_df.at[index, 'portfolio_holding'] = str(result.portfolio_holding)
            else:
                # This should never happen if our validation is complete
                annotated_df.at[index, 'validation_status'] = "ERROR_NOT_PROCESSED"
                self.logger.error(f"Entry not found in validation results: {lookup_key}")

        return annotated_df

    def _create_results_dataframe(self, results: List[ValidationResult]) -> pd.DataFrame:
        """Create a DataFrame from validation results"""
        if not results:
            # Return empty DataFrame with proper columns
            return pd.DataFrame(columns=[
                'symbol', 'type', 'al_symbol', 'has_price_data', 'portfolio_holding',
                'composite_key', 'change_type', 'explanation', 'explained',
                'corporate_action_type', 'corporate_action_date', 'confidence',
                'legitimacy_passed', 'legitimacy_issues', 'priority_for_review',
                'portfolio_impact_reason', 'details'
            ])

        data = []
        for r in results:
            row = {
                'symbol': r.symbol,
                'type': r.type,
                'al_symbol': r.al_symbol,
                'has_price_data': r.has_price_data,
                'portfolio_holding': r.portfolio_holding,
                'composite_key': r.composite_key,
                'change_type': r.change_type,
                'explanation': r.explanation,
                'explained': r.explained,
                'corporate_action_type': r.corporate_action_type or '',
                'corporate_action_date': r.corporate_action_date or '',
                'confidence': r.confidence,
                'legitimacy_passed': r.legitimacy_passed,
                'legitimacy_issues': r.legitimacy_issues or '',
                'priority_for_review': r.priority_for_review,
                'portfolio_impact_reason': r.portfolio_impact_reason or '',
                'details': str(r.details) if r.details else ''
            }
            data.append(row)

        df = pd.DataFrame(data)

        # Sort by priority and portfolio impact
        priority_order = {'ULTRA_HIGH': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        df['priority_sort'] = df['priority_for_review'].map(priority_order)
        df = df.sort_values(['portfolio_holding', 'priority_sort', 'symbol'], ascending=[False, True, True])
        df = df.drop('priority_sort', axis=1)

        return df

    def _create_summary(self, timestamp, truly_explained, failed_legitimacy,
                        ultra_high, high, medium, low) -> dict:
        """Create summary treating failed legitimacy as requiring investigation"""

        total_entries = len(self.validation_results)
        total_needing_review = len(failed_legitimacy) + len(ultra_high) + len(high) + len(medium) + len(low)

        return {
            'timestamp': timestamp,
            'total_entries_processed': total_entries,
            'truly_explained': len(truly_explained),
            'failed_legitimacy_needs_investigation': len(failed_legitimacy),
            'manual_review_needed': total_needing_review,
            'explanation_rate': (len(truly_explained) / total_entries * 100) if total_entries else 0,
            'investigation_rate': (total_needing_review / total_entries * 100) if total_entries else 0,
            'priority_breakdown': {
                'ultra_high': len(ultra_high),
                'high': len(high),
                'medium': len(medium),
                'low': len(low)
            },
            'legitimacy_issues': len(failed_legitimacy),
            'portfolio_impact': len([r for r in self.validation_results if r.portfolio_holding]),
            'critical_findings': {
                'failed_legitimacy_with_portfolio_impact': len([r for r in failed_legitimacy if r.portfolio_holding]),
                'unexplained_portfolio_changes': len([r for r in ultra_high if r.portfolio_holding and not r.explained])
            }
        }