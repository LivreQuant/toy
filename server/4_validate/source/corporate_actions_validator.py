#!/usr/bin/env python3
"""
Enhanced Corporate Actions Validator with portfolio impact checking
"""

import os
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
from typing import List
from config import config
from master_loader import MasterFileLoader
from legitimacy_checker import LegitimacyChecker
from portfolio_checker import PortfolioChecker
from validation_result import ValidationResult


class CorporateActionsValidator:
    """Enhanced validator with portfolio impact checking"""

    def __init__(self, portfolio_symbols: List[str] = None):
        """Initialize the validator with optional portfolio symbols"""
        # Setup logging
        self.setup_logging()

        # Load master files for legitimacy checks
        self.master_loader = MasterFileLoader()

        # Initialize legitimacy checker
        self.legitimacy_checker = LegitimacyChecker(self.master_loader)

        # Initialize portfolio checker
        self.portfolio_checker = PortfolioChecker(portfolio_symbols)

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
        self.portfolio_impacted_results: List[ValidationResult] = []

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
            df = pd.read_csv(file_path, sep="|", dtype=str, keep_default_na=False, na_values=[])
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
            'delistings': 'unified_delistings.csv',
            'ipos': 'unified_ipos.csv'
        }

        for action_type, filename in unified_files.items():
            file_path = os.path.join(ca_data_dir, filename)
            if os.path.exists(file_path):
                try:
                    df = pd.read_csv(file_path, sep="|", dtype=str, keep_default_na=False, na_values=[])
                    setattr(self, f"{action_type}_df", df)
                    self.logger.info(f"Loaded {len(df)} {action_type} records from {filename}")
                except Exception as e:
                    self.logger.error(f"Error loading {filename}: {e}")
            else:
                self.logger.warning(f"Unified file not found: {file_path}")

    def validate_new_entries(self) -> List[ValidationResult]:
        """Validate new entries against corporate actions with legitimacy checks"""
        results = []

        self.logger.info(f"Validating {len(self.new_entries_df)} new entries...")

        for _, row in self.new_entries_df.iterrows():
            symbol = row.get('symbol', '')
            type_val = row.get('type', '')
            al_symbol = row.get('al_symbol', '')
            composite_key = row.get('composite_key', '')

            # Check for symbol changes (new symbol appearing)
            symbol_change_explanation = self.check_for_symbol_change_new(symbol, row)
            if symbol_change_explanation:
                # Apply legitimacy check
                symbol_change_explanation = self.legitimacy_checker.apply_legitimacy_check(symbol_change_explanation)
                results.append(symbol_change_explanation)
                continue

            # Check for IPOs
            ipo_explanation = self.check_for_ipo(symbol, row)
            if ipo_explanation:
                # Apply legitimacy check
                ipo_explanation = self.legitimacy_checker.apply_legitimacy_check(ipo_explanation)
                results.append(ipo_explanation)
                continue

            # Check for spinoffs (new symbol from spinoff)
            spinoff_explanation = self.check_for_spinoff_new(symbol, row)
            if spinoff_explanation:
                # Apply legitimacy check
                spinoff_explanation = self.legitimacy_checker.apply_legitimacy_check(spinoff_explanation)
                results.append(spinoff_explanation)
                continue

            # If no explanation found
            unexplained_result = ValidationResult(
                symbol=symbol,
                type=type_val,
                al_symbol=al_symbol,
                composite_key=composite_key,
                change_type='NEW_ENTRY',
                explanation='No corporate action found to explain new entry',
                explained=False,
                confidence=0.0,
                legitimacy_passed=True  # No corporate action to validate
            )
            results.append(unexplained_result)

        return results

    def validate_missing_entries(self) -> List[ValidationResult]:
        """Validate missing entries against corporate actions with legitimacy checks"""
        results = []

        self.logger.info(f"Validating {len(self.missing_entries_df)} missing entries...")

        for _, row in self.missing_entries_df.iterrows():
            symbol = row.get('symbol', '')
            type_val = row.get('type', '')
            al_symbol = row.get('al_symbol', '')
            composite_key = row.get('composite_key', '')

            # Check for symbol changes (old symbol disappearing)
            symbol_change_explanation = self.check_for_symbol_change_missing(symbol, row)
            if symbol_change_explanation:
                # Apply legitimacy check
                symbol_change_explanation = self.legitimacy_checker.apply_legitimacy_check(symbol_change_explanation)
                results.append(symbol_change_explanation)
                continue

            # Check for delistings
            delisting_explanation = self.check_for_delisting(symbol, row)
            if delisting_explanation:
                # Apply legitimacy check
                delisting_explanation = self.legitimacy_checker.apply_legitimacy_check(delisting_explanation)
                results.append(delisting_explanation)
                continue

            # Check for mergers (target company)
            merger_explanation = self.check_for_merger_missing(symbol, row)
            if merger_explanation:
                # Apply legitimacy check
                merger_explanation = self.legitimacy_checker.apply_legitimacy_check(merger_explanation)
                results.append(merger_explanation)
                continue

            # If no explanation found
            unexplained_result = ValidationResult(
                symbol=symbol,
                type=type_val,
                al_symbol=al_symbol,
                composite_key=composite_key,
                change_type='MISSING_ENTRY',
                explanation='No corporate action found to explain missing entry',
                explained=False,
                confidence=0.0,
                legitimacy_passed=True  # No corporate action to validate
            )
            results.append(unexplained_result)

        return results

    # ... (keep all the existing check methods: check_for_ipo, check_for_symbol_change_new, etc.)

    def check_for_ipo(self, symbol: str, row: pd.Series) -> ValidationResult:
        """Check if new entry can be explained by an IPO"""
        if not self.ipos_df.empty:
            ipo_matches = self.ipos_df[self.ipos_df['master_symbol'] == symbol]

            if not ipo_matches.empty:
                ipo_action = ipo_matches.iloc[0]
                return ValidationResult(
                    symbol=symbol,
                    type=row.get('type', ''),
                    al_symbol=row.get('al_symbol', ''),
                    composite_key=row.get('composite_key', ''),
                    change_type='NEW_ENTRY',
                    explanation=f'IPO detected: {symbol} went public',
                    explained=True,
                    corporate_action_type='IPO',
                    corporate_action_date=ipo_action.get('list_date', ''),
                    confidence=float(ipo_action.get('overall_confidence', 0.8)),
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
                    type=row.get('type', ''),
                    al_symbol=row.get('al_symbol', ''),
                    composite_key=row.get('composite_key', ''),
                    change_type='NEW_ENTRY',
                    explanation=f'Symbol change detected: {change_action.get("old_symbol", "unknown")} changed to {symbol}',
                    explained=True,
                    corporate_action_type='SYMBOL_CHANGE',
                    corporate_action_date=change_action.get('change_date', ''),
                    confidence=float(change_action.get('overall_confidence', 0.9)),
                    details={'source': change_action.get('source'), 'old_symbol': change_action.get('old_symbol'),
                             'new_symbol': symbol, 'action_data': change_action.to_dict()}
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
                    type=row.get('type', ''),
                    al_symbol=row.get('al_symbol', ''),
                    composite_key=row.get('composite_key', ''),
                    change_type='NEW_ENTRY',
                    explanation=f'Spinoff detected: {symbol} spun off from {spinoff_action.get("master_symbol", "unknown")}',
                    explained=True,
                    corporate_action_type='SPINOFF',
                    corporate_action_date=spinoff_action.get('ex_date', ''),
                    confidence=float(spinoff_action.get('overall_confidence', 0.85)),
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
                    type=row.get('type', ''),
                    al_symbol=row.get('al_symbol', ''),
                    composite_key=row.get('composite_key', ''),
                    change_type='MISSING_ENTRY',
                    explanation=f'Delisting detected: {symbol} - {delisting_action.get("delisting_reason", "delisted")}',
                    explained=True,
                    corporate_action_type='DELISTING',
                    corporate_action_date=delisting_action.get('delisting_date', ''),
                    confidence=float(delisting_action.get('overall_confidence', 0.9)),
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
                    type=row.get('type', ''),
                    al_symbol=row.get('al_symbol', ''),
                    composite_key=row.get('composite_key', ''),
                    change_type='MISSING_ENTRY',
                    explanation=f'Merger detected: {symbol} was acquired by {merger_action.get("acquirer_symbol", "unknown")}',
                    explained=True,
                    corporate_action_type='MERGER',
                    corporate_action_date=merger_action.get('ex_date', ''),
                    confidence=float(merger_action.get('overall_confidence', 0.9)),
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
                    type=row.get('type', ''),
                    al_symbol=row.get('al_symbol', ''),
                    composite_key=row.get('composite_key', ''),
                    change_type='MISSING_ENTRY',
                    explanation=f'Symbol change detected: {symbol} changed to {change_action.get("new_symbol", "unknown")}',
                    explained=True,
                    corporate_action_type='SYMBOL_CHANGE',
                    corporate_action_date=change_action.get('change_date', ''),
                    confidence=float(change_action.get('overall_confidence', 0.9)),
                    details={'source': change_action.get('source'), 'new_symbol': change_action.get('new_symbol'),
                             'old_symbol': symbol, 'action_data': change_action.to_dict()}
                )

        return None

    def run_validation(self) -> tuple[List[ValidationResult], List[ValidationResult]]:
        """Run complete validation process with enhanced priority assignment"""
        self.logger.info("Starting corporate actions validation with legitimacy and portfolio checks...")

        # Validate new entries
        new_results = self.validate_new_entries()

        # Validate missing entries
        missing_results = self.validate_missing_entries()

        # Store results
        self.validation_results = new_results + missing_results

        # Initialize priority assigner and assign priorities
        from priority_assigner import PriorityAssigner
        priority_assigner = PriorityAssigner()
        self.validation_results = priority_assigner.assign_priorities(self.validation_results)

        # Check for portfolio impact (now integrated with priority assignment)
        self.portfolio_impacted_results = [
            r for r in self.validation_results
            if r.portfolio_holding
        ]

        # Generate priority summary for logging
        priority_summary = priority_assigner.generate_priority_summary(self.validation_results)

        # Log comprehensive summary
        self._log_validation_summary(priority_summary)

        return new_results, missing_results

    def _log_validation_summary(self, priority_summary: dict):
        """Log detailed validation summary with business context"""
        severity = priority_summary["alert_severity"]
        portfolio_impact = priority_summary["portfolio_impact"]
        priority_dist = priority_summary["priority_distribution"]
        risk_metrics = priority_summary["risk_metrics"]

        self.logger.info(f"=== VALIDATION COMPLETE - Alert Severity: {severity} ===")

        # Portfolio impact logging
        if portfolio_impact["total_portfolio_affected"] > 0:
            self.logger.critical(
                f"PORTFOLIO IMPACT: {portfolio_impact['total_portfolio_affected']} portfolio symbols affected"
            )

            if portfolio_impact["missing_portfolio_symbols"] > 0:
                self.logger.critical(
                    f"  🚨 {portfolio_impact['missing_portfolio_symbols']} portfolio symbols MISSING from master list"
                )

            if portfolio_impact["unexplained_portfolio"] > 0:
                self.logger.critical(
                    f"  ❓ {portfolio_impact['unexplained_portfolio']} portfolio changes UNEXPLAINED"
                )
        else:
            self.logger.info("✅ No portfolio symbols affected")

        # Priority distribution logging
        self.logger.info(f"Priority Distribution:")
        self.logger.info(f"  ULTRA_HIGH (Portfolio): {priority_dist['ULTRA_HIGH']}")
        self.logger.info(f"  HIGH (Price data, unexplained): {priority_dist['HIGH']}")
        self.logger.info(f"  MEDIUM (Legitimacy failed): {priority_dist['MEDIUM']}")
        self.logger.info(f"  LOW (No price data, unexplained): {priority_dist['LOW']}")
        self.logger.info(f"  EXPLAINED (No review needed): {priority_dist['EXPLAINED']}")

        # Risk metrics
        self.logger.info(f"Risk Metrics:")
        self.logger.info(f"  Manual review rate: {risk_metrics['manual_review_rate']:.1f}%")
        self.logger.info(f"  Explanation success rate: {risk_metrics['explanation_success_rate']:.1f}%")
        self.logger.info(f"  Portfolio impact rate: {risk_metrics['portfolio_impact_rate']:.1f}%")

        # Final alert
        if severity in ["CRITICAL", "HIGH"]:
            self.logger.critical(
                f"⚠️ IMMEDIATE ACTION REQUIRED - Severity: {severity} ⚠️"
            )

    def get_portfolio_alert_summary(self) -> dict:
        """Get portfolio alert summary for external reporting"""
        return self.portfolio_checker.generate_portfolio_alert_summary(self.portfolio_impacted_results)

    def get_results_exporter(self) -> 'ResultsExporter':
        """Get results exporter with access to original files"""
        from results_exporter import ResultsExporter
        return ResultsExporter(self.validation_results, self.new_entries_df, self.missing_entries_df)