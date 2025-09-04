#!/usr/bin/env python3
"""
Portfolio holdings checker for ultra-high priority validation
"""

import pandas as pd
import logging
from typing import List, Set
from pathlib import Path
from validation_result import ValidationResult


class PortfolioChecker:
    """Checks validation results against portfolio holdings for ultra-high priority flagging"""

    def __init__(self, portfolio_symbols: List[str] = None):
        self.logger = logging.getLogger(__name__)

        # Use provided portfolio symbols or load from file/create dummy
        if portfolio_symbols:
            self.portfolio_symbols = set(portfolio_symbols)
        else:
            self.portfolio_symbols = self._load_portfolio_symbols()

        self.logger.info(f"Loaded {len(self.portfolio_symbols)} portfolio symbols for ultra-high priority checking")

    def _load_portfolio_symbols(self) -> Set[str]:
        """Load portfolio symbols from file or create dummy list"""
        # Try to load from a portfolio file first
        portfolio_file_paths = [
            "portfolio_holdings.csv",
            "data/portfolio_holdings.csv",
            "../data/portfolio_holdings.csv"
        ]

        for file_path in portfolio_file_paths:
            if Path(file_path).exists():
                try:
                    df = pd.read_csv(file_path, dtype=str, keep_default_na=False, na_values=[], sep="|")
                    # Assume the CSV has a 'symbol' column
                    symbols = set(df['symbol'].astype(str).str.upper().tolist())
                    self.logger.info(f"Loaded portfolio symbols from {file_path}")
                    return symbols
                except Exception as e:
                    self.logger.warning(f"Failed to load portfolio from {file_path}: {e}")

        # If no file found, create a realistic dummy portfolio
        dummy_portfolio = self._create_dummy_portfolio()
        self.logger.warning(f"No portfolio file found. Using dummy portfolio with {len(dummy_portfolio)} symbols")
        return dummy_portfolio

    def _create_dummy_portfolio(self) -> Set[str]:
        """Create a realistic dummy portfolio for testing"""
        # Mix of large caps, mid caps, some that might have corporate actions
        dummy_symbols = {
            # Large cap tech
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA',

            # Large cap traditional
            'JNJ', 'JPM', 'V', 'PG', 'UNH', 'HD', 'MA', 'DIS', 'NFLX', 'CRM',

            # Mid caps that might be more volatile
            'SQ', 'ROKU', 'PINS', 'SNAP', 'UBER', 'LYFT', 'SPOT', 'ZM', 'DOCU',

            # Some symbols that might undergo corporate actions
            'XOM', 'CVX', 'WFC', 'BAC', 'GE', 'F', 'GM', 'AAL', 'UAL', 'CCL',

            # REITs and utilities
            'AMT', 'PLD', 'CCI', 'EQIX', 'SO', 'NEE', 'DUK', 'AEP',

            # Healthcare and biotech
            'PFE', 'ABBV', 'TMO', 'ABT', 'MRK', 'GILD', 'BIIB', 'AMGN',

            # Financials
            'GS', 'MS', 'C', 'AXP', 'BLK', 'SCHW', 'TFC', 'USB',

            # Consumer discretionary
            'AMZN', 'TSLA', 'NKE', 'SBUX', 'MCD', 'LOW', 'TJX', 'BKNG',

            # Some smaller/riskier names that might be more prone to corp actions
            'PLUG', 'FCEL', 'SPCE', 'NKLA', 'RIDE', 'WKHS', 'HYLN', 'QS'
        }

        return dummy_symbols

    def check_portfolio_impact(self, validation_results: List[ValidationResult]) -> List[ValidationResult]:
        """Check validation results for portfolio impact and update priority"""
        portfolio_impacted_results = []

        for result in validation_results:
            # Check if this symbol is in our portfolio
            if result.symbol.upper() in self.portfolio_symbols:
                # This is a portfolio holding - mark as ULTRA_HIGH priority
                result.priority_for_review = "ULTRA_HIGH"
                result.portfolio_holding = True
                result.portfolio_impact_reason = self._determine_portfolio_impact_reason(result)

                portfolio_impacted_results.append(result)

                self.logger.warning(f"PORTFOLIO IMPACT: {result.symbol} - {result.portfolio_impact_reason}")
            else:
                # Mark as not a portfolio holding
                result.portfolio_holding = False

        return portfolio_impacted_results

    def _determine_portfolio_impact_reason(self, result: ValidationResult) -> str:
        """Determine the specific reason for portfolio impact"""
        reasons = []

        if not result.explained:
            reasons.append("UNEXPLAINED CHANGE")

        if result.explained and not result.legitimacy_passed:
            reasons.append("FAILED LEGITIMACY CHECK")

        if result.change_type == "MISSING_ENTRY":
            reasons.append("SYMBOL DISAPPEARED")

        if result.change_type == "NEW_ENTRY":
            reasons.append("NEW SYMBOL APPEARED")

        if result.has_price_data:
            reasons.append("HAS PRICE DATA")

        if result.corporate_action_type:
            reasons.append(f"CORPORATE ACTION: {result.corporate_action_type}")

        return " | ".join(reasons) if reasons else "UNKNOWN IMPACT"

    def generate_portfolio_alert_summary(self, portfolio_impacted_results: List[ValidationResult]) -> dict:
        """Generate detailed portfolio impact summary for alerts"""
        if not portfolio_impacted_results:
            return {
                'total_portfolio_symbols': len(self.portfolio_symbols),
                'impacted_symbols': 0,
                'impact_summary': "No portfolio symbols affected",
                'action_required': False
            }

        # Categorize impacts
        missing_symbols = [r for r in portfolio_impacted_results if r.change_type == "MISSING_ENTRY"]
        new_symbols = [r for r in portfolio_impacted_results if r.change_type == "NEW_ENTRY"]
        unexplained = [r for r in portfolio_impacted_results if not r.explained]
        failed_legitimacy = [r for r in portfolio_impacted_results if r.explained and not r.legitimacy_passed]

        # Corporate action breakdown
        corporate_actions = {}
        for result in portfolio_impacted_results:
            if result.corporate_action_type:
                action_type = result.corporate_action_type
                corporate_actions[action_type] = corporate_actions.get(action_type, 0) + 1

        summary = {
            'total_portfolio_symbols': len(self.portfolio_symbols),
            'impacted_symbols': len(portfolio_impacted_results),
            'impact_rate': (len(portfolio_impacted_results) / len(self.portfolio_symbols)) * 100,
            'missing_symbols': len(missing_symbols),
            'new_symbols': len(new_symbols),
            'unexplained_changes': len(unexplained),
            'failed_legitimacy': len(failed_legitimacy),
            'corporate_actions_found': corporate_actions,
            'action_required': len(portfolio_impacted_results) > 0,
            'severity': self._determine_alert_severity(portfolio_impacted_results),
            'impacted_symbol_list': [r.symbol for r in portfolio_impacted_results],
            'detailed_impacts': [
                {
                    'symbol': r.symbol,
                    'change_type': r.change_type,
                    'explanation': r.explanation,
                    'corporate_action': r.corporate_action_type,
                    'legitimacy_passed': r.legitimacy_passed,
                    'has_price_data': r.has_price_data,
                    'impact_reason': r.portfolio_impact_reason
                }
                for r in portfolio_impacted_results
            ]
        }

        return summary

    def _determine_alert_severity(self, portfolio_impacted_results: List[ValidationResult]) -> str:
        """Determine overall alert severity based on portfolio impacts"""
        if not portfolio_impacted_results:
            return "NONE"

        # Check for critical issues
        unexplained_with_price_data = [r for r in portfolio_impacted_results
                                       if not r.explained and r.has_price_data]
        missing_unexplained = [r for r in portfolio_impacted_results
                               if r.change_type == "MISSING_ENTRY" and not r.explained]
        failed_legitimacy = [r for r in portfolio_impacted_results
                             if r.explained and not r.legitimacy_passed]

        if unexplained_with_price_data or missing_unexplained:
            return "CRITICAL"
        elif failed_legitimacy or len(portfolio_impacted_results) > 5:
            return "HIGH"
        elif len(portfolio_impacted_results) > 0:
            return "MEDIUM"
        else:
            return "LOW"

    def save_portfolio_holdings(self, file_path: str):
        """Save current portfolio holdings to file for future use"""
        try:
            df = pd.DataFrame({'symbol': sorted(list(self.portfolio_symbols))})
            df.to_csv(file_path, index=False)
            self.logger.info(f"Saved {len(self.portfolio_symbols)} portfolio symbols to {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to save portfolio holdings: {e}")

    def add_portfolio_symbols(self, symbols: List[str]):
        """Add new symbols to portfolio holdings"""
        new_symbols = set(s.upper() for s in symbols)
        added_symbols = new_symbols - self.portfolio_symbols
        self.portfolio_symbols.update(new_symbols)

        if added_symbols:
            self.logger.info(f"Added {len(added_symbols)} new portfolio symbols: {sorted(added_symbols)}")

    def remove_portfolio_symbols(self, symbols: List[str]):
        """Remove symbols from portfolio holdings"""
        remove_symbols = set(s.upper() for s in symbols)
        removed_symbols = self.portfolio_symbols & remove_symbols
        self.portfolio_symbols -= remove_symbols

        if removed_symbols:
            self.logger.info(f"Removed {len(removed_symbols)} portfolio symbols: {sorted(removed_symbols)}")