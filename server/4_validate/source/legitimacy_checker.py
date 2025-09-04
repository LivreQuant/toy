#!/usr/bin/env python3
"""
Legitimacy checker for corporate actions validation
"""

import logging
from typing import Tuple
from master_loader import MasterFileLoader
from validation_result import ValidationResult


class LegitimacyChecker:
    """Performs legitimacy checks on corporate actions"""

    def __init__(self, master_loader: MasterFileLoader):
        self.logger = logging.getLogger(__name__)
        self.master_loader = master_loader

    def check_spinoff_legitimacy(self, validation_result: ValidationResult, parent_symbol: str) -> Tuple[bool, str]:
        """
        Check spinoff legitimacy:
        - Original symbol must have existed in previous day's master list
        """
        if not parent_symbol:
            return False, "No parent symbol provided for spinoff"

        if not self.master_loader.symbol_existed_previous_day(parent_symbol):
            return False, f"Parent symbol '{parent_symbol}' did not exist in previous day's master list"

        self.logger.info(f"Spinoff legitimacy check passed: {parent_symbol} -> {validation_result.symbol}")
        return True, "Spinoff legitimacy verified"

    def check_symbol_change_legitimacy(self, validation_result: ValidationResult, old_symbol: str, new_symbol: str) -> \
    Tuple[bool, str]:
        """
        Check symbol change legitimacy:
        - For new entries: old symbol must have existed in previous day's master list
        - For missing entries: old symbol must have existed in previous day's master list
        """
        if validation_result.change_type == "NEW_ENTRY":
            # Check if old symbol existed in previous day
            if not self.master_loader.symbol_existed_previous_day(old_symbol):
                return False, f"Old symbol '{old_symbol}' did not exist in previous day's master list for symbol change to '{new_symbol}'"

        elif validation_result.change_type == "MISSING_ENTRY":
            # For missing entries, the old symbol should have existed in previous day
            if not self.master_loader.symbol_existed_previous_day(old_symbol):
                return False, f"Symbol '{old_symbol}' did not exist in previous day's master list for symbol change"

        self.logger.info(f"Symbol change legitimacy check passed: {old_symbol} -> {new_symbol}")
        return True, "Symbol change legitimacy verified"

    def check_merger_legitimacy(self, validation_result: ValidationResult, acquirer_symbol: str,
                                acquiree_symbol: str) -> Tuple[bool, str]:
        """
        Check merger legitimacy:
        - Acquiree symbol must have existed in previous day's master list
        - Acquirer symbol should exist in current day's master list
        """
        issues = []

        # Check if acquiree existed in previous day
        if not self.master_loader.symbol_existed_previous_day(acquiree_symbol):
            issues.append(f"Acquiree symbol '{acquiree_symbol}' did not exist in previous day's master list")

        # Check if acquirer exists in current day (where the old symbol should go)
        if not self.master_loader.symbol_exists_current_day(acquirer_symbol):
            issues.append(f"Acquirer symbol '{acquirer_symbol}' does not exist in current day's master list")

        if issues:
            return False, "; ".join(issues)

        self.logger.info(f"Merger legitimacy check passed: {acquiree_symbol} acquired by {acquirer_symbol}")
        return True, "Merger legitimacy verified"

    def check_ipo_legitimacy(self, validation_result: ValidationResult) -> Tuple[bool, str]:
        """
        Check IPO legitimacy:
        - Symbol should NOT have existed in previous day's master list
        """
        if self.master_loader.symbol_existed_previous_day(validation_result.symbol):
            return False, f"IPO symbol '{validation_result.symbol}' already existed in previous day's master list"

        self.logger.info(f"IPO legitimacy check passed: {validation_result.symbol}")
        return True, "IPO legitimacy verified"

    def check_delisting_legitimacy(self, validation_result: ValidationResult) -> Tuple[bool, str]:
        """
        Check delisting legitimacy:
        - Symbol must have existed in previous day's master list
        """
        if not self.master_loader.symbol_existed_previous_day(validation_result.symbol):
            return False, f"Delisted symbol '{validation_result.symbol}' did not exist in previous day's master list"

        self.logger.info(f"Delisting legitimacy check passed: {validation_result.symbol}")
        return True, "Delisting legitimacy verified"

    def apply_legitimacy_check(self, validation_result: ValidationResult) -> ValidationResult:
        """Apply appropriate legitimacy check based on corporate action type"""
        if not validation_result.explained:
            # No corporate action found, so no legitimacy check needed
            validation_result.legitimacy_passed = True
            return validation_result

        legitimacy_passed = False
        legitimacy_issues = ""

        try:
            if validation_result.corporate_action_type == "SPINOFF":
                parent_symbol = validation_result.details.get('parent_company', '') if validation_result.details else ''
                legitimacy_passed, legitimacy_issues = self.check_spinoff_legitimacy(validation_result, parent_symbol)

            elif validation_result.corporate_action_type == "SYMBOL_CHANGE":
                old_symbol = validation_result.details.get('old_symbol', '') if validation_result.details else ''
                new_symbol = validation_result.details.get('new_symbol', '') if validation_result.details else ''

                # Determine which symbol to use based on change type
                if validation_result.change_type == "NEW_ENTRY":
                    legitimacy_passed, legitimacy_issues = self.check_symbol_change_legitimacy(validation_result,
                                                                                               old_symbol,
                                                                                               validation_result.symbol)
                else:  # MISSING_ENTRY
                    legitimacy_passed, legitimacy_issues = self.check_symbol_change_legitimacy(validation_result,
                                                                                               validation_result.symbol,
                                                                                               new_symbol)

            elif validation_result.corporate_action_type == "MERGER":
                acquirer = validation_result.details.get('acquirer', '') if validation_result.details else ''
                legitimacy_passed, legitimacy_issues = self.check_merger_legitimacy(validation_result, acquirer,
                                                                                    validation_result.symbol)

            elif validation_result.corporate_action_type == "IPO":
                legitimacy_passed, legitimacy_issues = self.check_ipo_legitimacy(validation_result)

            elif validation_result.corporate_action_type == "DELISTING":
                legitimacy_passed, legitimacy_issues = self.check_delisting_legitimacy(validation_result)

            else:
                legitimacy_passed = True  # Unknown action type, assume legitimate

        except Exception as e:
            self.logger.error(f"Error during legitimacy check for {validation_result.symbol}: {e}")
            legitimacy_passed = False
            legitimacy_issues = f"Error during legitimacy check: {str(e)}"

        validation_result.legitimacy_passed = legitimacy_passed
        validation_result.legitimacy_issues = legitimacy_issues if not legitimacy_passed else None

        return validation_result