#!/usr/bin/env python3
"""
Enhanced priority assignment for corporate actions validation
"""

import logging
from typing import List
from validation_result import ValidationResult


class PriorityAssigner:
    """Assigns priority levels based on portfolio impact, price data, and explanation status"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def assign_priorities(self, validation_results: List[ValidationResult]) -> List[ValidationResult]:
        """
        Complete priority assignment based on business impact:

        ULTRA_HIGH: Portfolio holdings (immediate financial impact)
        HIGH: Has price data but unexplained (operational risk)
        MEDIUM: Explained but failed legitimacy (data integrity risk)
        LOW: No price data and unexplained (low operational impact)
        """

        for result in validation_results:
            # Start with base priority
            result.priority_for_review = self._calculate_base_priority(result)

            # Portfolio holdings override everything else
            if result.portfolio_holding:
                result.priority_for_review = "ULTRA_HIGH"
                result.portfolio_impact_reason = self._determine_portfolio_impact_reason(result)

                self.logger.critical(
                    f"PORTFOLIO IMPACT: {result.symbol} ({result.change_type}) - "
                    f"{result.portfolio_impact_reason}"
                )

            # Log high-priority non-portfolio items
            elif result.priority_for_review == "HIGH":
                self.logger.warning(
                    f"HIGH PRIORITY: {result.symbol} - Unexplained with price data"
                )

        return validation_results

    def _calculate_base_priority(self, result: ValidationResult) -> str:
        """Calculate base priority before portfolio override"""

        # Explained and passed legitimacy = no manual review needed
        if result.explained and result.legitimacy_passed:
            return "EXPLAINED"  # This won't be in manual review files

        # Explained but failed legitimacy = data integrity issue
        if result.explained and not result.legitimacy_passed:
            return "MEDIUM"

        # Unexplained cases
        if not result.explained:
            if result.has_price_data:
                return "HIGH"  # Operational risk - affects tradeable securities
            else:
                return "LOW"  # Low impact - no price data means limited operational impact

        return "LOW"

    def _determine_portfolio_impact_reason(self, result: ValidationResult) -> str:
        """Determine specific reason for portfolio impact with business context"""
        reasons = []

        # Critical scenarios first
        if result.change_type == "MISSING_ENTRY":
            reasons.append("PORTFOLIO SYMBOL DISAPPEARED")
            if result.has_price_data:
                reasons.append("TRADING IMPACT")

        if result.change_type == "NEW_ENTRY":
            reasons.append("NEW PORTFOLIO-RELATED SYMBOL")

        # Explanation status
        if not result.explained:
            reasons.append("UNEXPLAINED CHANGE")
        elif not result.legitimacy_passed:
            reasons.append("SUSPICIOUS CORPORATE ACTION")

        # Data integrity
        if result.has_price_data:
            reasons.append("PRICE DATA AVAILABLE")

        # Corporate action context
        if result.corporate_action_type:
            reasons.append(f"CORP ACTION: {result.corporate_action_type}")

        return " | ".join(reasons) if reasons else "PORTFOLIO HOLDING AFFECTED"

    def generate_priority_summary(self, validation_results: List[ValidationResult]) -> dict:
        """Generate summary of priority distribution for reporting"""

        # Count by priority
        priority_counts = {
            "ULTRA_HIGH": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
            "EXPLAINED": 0
        }

        portfolio_impact = {
            "total_portfolio_affected": 0,
            "missing_portfolio_symbols": 0,
            "new_portfolio_symbols": 0,
            "unexplained_portfolio": 0,
            "portfolio_with_price_data": 0
        }

        for result in validation_results:
            priority = result.priority_for_review
            if priority in priority_counts:
                priority_counts[priority] += 1

            if result.portfolio_holding:
                portfolio_impact["total_portfolio_affected"] += 1

                if result.change_type == "MISSING_ENTRY":
                    portfolio_impact["missing_portfolio_symbols"] += 1
                elif result.change_type == "NEW_ENTRY":
                    portfolio_impact["new_portfolio_symbols"] += 1

                if not result.explained:
                    portfolio_impact["unexplained_portfolio"] += 1

                if result.has_price_data:
                    portfolio_impact["portfolio_with_price_data"] += 1

        # Calculate risk metrics
        total_entries = len(validation_results)
        manual_review_needed = (
                priority_counts["ULTRA_HIGH"] +
                priority_counts["HIGH"] +
                priority_counts["MEDIUM"] +
                priority_counts["LOW"]
        )

        return {
            "priority_distribution": priority_counts,
            "portfolio_impact": portfolio_impact,
            "risk_metrics": {
                "total_entries": total_entries,
                "manual_review_needed": manual_review_needed,
                "manual_review_rate": (manual_review_needed / total_entries * 100) if total_entries else 0,
                "portfolio_impact_rate": (
                            portfolio_impact["total_portfolio_affected"] / total_entries * 100) if total_entries else 0,
                "explanation_success_rate": (priority_counts["EXPLAINED"] / total_entries * 100) if total_entries else 0
            },
            "alert_severity": self._determine_alert_severity(portfolio_impact, priority_counts)
        }

    def _determine_alert_severity(self, portfolio_impact: dict, priority_counts: dict) -> str:
        """Determine overall system alert severity"""

        # Critical: Portfolio symbols missing or unexplained
        if (portfolio_impact["missing_portfolio_symbols"] > 0 or
                portfolio_impact["unexplained_portfolio"] > 0):
            return "CRITICAL"

        # High: Portfolio affected or many high-priority items
        if (portfolio_impact["total_portfolio_affected"] > 0 or
                priority_counts["HIGH"] > 10):
            return "HIGH"

        # Medium: Some manual review needed
        if priority_counts["ULTRA_HIGH"] + priority_counts["HIGH"] + priority_counts["MEDIUM"] > 0:
            return "MEDIUM"

        return "LOW"