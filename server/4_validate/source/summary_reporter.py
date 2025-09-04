#!/usr/bin/env python3
"""
Enhanced summary reporter with portfolio impact prioritization
"""

import logging
from typing import List
from validation_result import ValidationResult


class SummaryReporter:
    """Enhanced summary reporter with portfolio impact focus"""

    def __init__(self, validation_results: List[ValidationResult]):
        self.validation_results = validation_results
        self.logger = logging.getLogger(__name__)

    def print_summary(self):
        """Print enhanced validation summary with portfolio impact emphasis"""
        if not self.validation_results:
            print("No validation results to summarize.")
            return

        # Categorize results with portfolio priority
        ultra_high_priority = [r for r in self.validation_results if r.priority_for_review == "ULTRA_HIGH"]
        explained_passed = [r for r in self.validation_results if
                            r.explained and r.legitimacy_passed and r.priority_for_review != "ULTRA_HIGH"]
        explained_failed = [r for r in self.validation_results if
                            r.explained and not r.legitimacy_passed and r.priority_for_review != "ULTRA_HIGH"]
        high_priority = [r for r in self.validation_results if not r.explained and r.priority_for_review == "HIGH"]
        medium_priority = [r for r in self.validation_results if not r.explained and r.priority_for_review == "MEDIUM"]
        low_priority = [r for r in self.validation_results if not r.explained and r.priority_for_review == "LOW"]

        # Portfolio analysis
        portfolio_holdings = [r for r in self.validation_results if r.portfolio_holding]
        portfolio_with_price_data = [r for r in portfolio_holdings if r.has_price_data]

        print("\n" + "=" * 120)
        print("🚨 ENHANCED CORPORATE ACTIONS VALIDATION WITH PORTFOLIO IMPACT ANALYSIS 🚨")
        print("=" * 120)

        # Portfolio Impact Alert Section
        if ultra_high_priority:
            print("🔴 PORTFOLIO IMPACT ALERT - IMMEDIATE ACTION REQUIRED 🔴")
            print(f"📊 {len(ultra_high_priority)} PORTFOLIO SYMBOLS AFFECTED")

            missing_portfolio = [r for r in ultra_high_priority if r.change_type == "MISSING_ENTRY"]
            new_portfolio = [r for r in ultra_high_priority if r.change_type == "NEW_ENTRY"]
            unexplained_portfolio = [r for r in ultra_high_priority if not r.explained]

            print(f"   • {len(missing_portfolio)} portfolio symbols MISSING from master list")
            print(f"   • {len(new_portfolio)} new portfolio-related symbols appeared")
            print(f"   • {len(unexplained_portfolio)} unexplained portfolio changes")
            print(f"   • {len([r for r in ultra_high_priority if r.has_price_data])} affected symbols have price data")

            print("\n🚨 CRITICAL PORTFOLIO ISSUES:")
            for result in ultra_high_priority:
                status_icon = "❌" if result.change_type == "MISSING_ENTRY" else "⚠️"
                price_status = "💰" if result.has_price_data else "📊"
                print(f"   {status_icon} {price_status} {result.symbol} - {result.portfolio_impact_reason}")
            print()
        else:
            print("✅ NO PORTFOLIO IMPACT DETECTED")
            print()

        # Overall Statistics
        print("📈 OVERALL VALIDATION STATISTICS:")
        print(f"Total entries analyzed: {len(self.validation_results)}")
        print(f"Portfolio holdings in analysis: {len(portfolio_holdings)}")
        print(
            f"Entries with price data (al_symbol): {len([r for r in self.validation_results if r.has_price_data])} ({len([r for r in self.validation_results if r.has_price_data]) / len(self.validation_results) * 100:.1f}%)")
        print()

        # Explanation Status
        print("🔍 EXPLANATION STATUS:")
        print(
            f"  ✅ Explained & legitimate: {len(explained_passed)} ({len(explained_passed) / len(self.validation_results) * 100:.1f}%)")
        print(
            f"  ⚠️  Explained but failed legitimacy: {len(explained_failed)} ({len(explained_failed) / len(self.validation_results) * 100:.1f}%)")
        print(
            f"  🔴 ULTRA HIGH Priority (Portfolio): {len(ultra_high_priority)} ({len(ultra_high_priority) / len(self.validation_results) * 100:.1f}%)")
        print(
            f"  🟠 HIGH Priority (manual review): {len(high_priority)} ({len(high_priority) / len(self.validation_results) * 100:.1f}%)")
        print(
            f"  🟡 MEDIUM Priority: {len(medium_priority)} ({len(medium_priority) / len(self.validation_results) * 100:.1f}%)")
        print(f"  🟢 LOW Priority: {len(low_priority)} ({len(low_priority) / len(self.validation_results) * 100:.1f}%)")
        print()

        # Legitimacy Issues
        if explained_failed:
            print("⚠️ LEGITIMACY ISSUES (NON-PORTFOLIO):")
            for result in explained_failed:
                print(f"   • {result.symbol} ({result.corporate_action_type}): {result.legitimacy_issues}")
            print()

        # Change Type Breakdown
        new_entries = [r for r in self.validation_results if r.change_type == 'NEW_ENTRY']
        missing_entries = [r for r in self.validation_results if r.change_type == 'MISSING_ENTRY']

        print("📊 CHANGE TYPE BREAKDOWN:")
        print("NEW ENTRIES:")
        new_explained = [r for r in new_entries if r.explained and r.legitimacy_passed]
        new_portfolio = [r for r in new_entries if r.portfolio_holding]
        print(
            f"  Total: {len(new_entries)} | Portfolio affected: {len(new_portfolio)} | Explained & legitimate: {len(new_explained)}")

        print("MISSING ENTRIES:")
        missing_explained = [r for r in missing_entries if r.explained and r.legitimacy_passed]
        missing_portfolio = [r for r in missing_entries if r.portfolio_holding]
        print(
            f"  Total: {len(missing_entries)} | Portfolio affected: {len(missing_portfolio)} | Explained & legitimate: {len(missing_explained)}")
        print()

        # Corporate Action Types
        if explained_passed or explained_failed:
            print("📋 CORPORATE ACTION TYPES FOUND:")
            action_counts = {}
            legitimacy_counts = {}
            portfolio_counts = {}

            for result in self.validation_results:
                if result.explained and result.corporate_action_type:
                    action_type = result.corporate_action_type
                    action_counts[action_type] = action_counts.get(action_type, 0) + 1

                    if action_type not in legitimacy_counts:
                        legitimacy_counts[action_type] = {'passed': 0, 'failed': 0}
                        portfolio_counts[action_type] = {'portfolio': 0, 'non_portfolio': 0}

                    if result.legitimacy_passed:
                        legitimacy_counts[action_type]['passed'] += 1
                    else:
                        legitimacy_counts[action_type]['failed'] += 1

                    if result.portfolio_holding:
                        portfolio_counts[action_type]['portfolio'] += 1
                    else:
                        portfolio_counts[action_type]['non_portfolio'] += 1

            for action_type, count in sorted(action_counts.items()):
                passed = legitimacy_counts[action_type]['passed']
                failed = legitimacy_counts[action_type]['failed']
                portfolio = portfolio_counts[action_type]['portfolio']
                portfolio_indicator = f" | 🚨 {portfolio} PORTFOLIO" if portfolio > 0 else ""
                print(f"  {action_type}: {count} total (✅{passed} legitimate, ⚠️{failed} failed){portfolio_indicator}")
            print()

        # Risk Assessment
        print("🎯 RISK ASSESSMENT & IMPACT:")
        trading_risk = len([r for r in ultra_high_priority if r.has_price_data])
        valuation_risk = len([r for r in ultra_high_priority if r.change_type == "MISSING_ENTRY" and r.has_price_data])

        print(
            f"  Trading Operations Risk: {'🔴 HIGH' if trading_risk > 0 else '🟢 LOW'} ({trading_risk} portfolio symbols with price data affected)")
        print(
            f"  Portfolio Valuation Risk: {'🔴 CRITICAL' if valuation_risk > 0 else '🟢 LOW'} ({valuation_risk} missing portfolio symbols with price data)")
        print(
            f"  Data Integrity Risk: {'🔴 HIGH' if explained_failed else '🟢 LOW'} ({len(explained_failed)} legitimacy failures)")
        print()

        # Action Items
        print("🎯 IMMEDIATE ACTION ITEMS:")
        action_items = []

        if ultra_high_priority:
            missing_critical = len([r for r in ultra_high_priority if r.change_type == "MISSING_ENTRY"])
            if missing_critical > 0:
                action_items.append(f"🚨 URGENT: Investigate {missing_critical} missing portfolio symbols")

            unexplained_critical = len([r for r in ultra_high_priority if not r.explained])
            if unexplained_critical > 0:
                action_items.append(f"🔍 PRIORITY: Review {unexplained_critical} unexplained portfolio changes")

            price_data_impact = len([r for r in ultra_high_priority if r.has_price_data])
            if price_data_impact > 0:
                action_items.append(
                    f"💰 FINANCIAL: Verify impact on {price_data_impact} portfolio positions with price data")

        if explained_failed:
            action_items.append(f"⚠️ Address {len(explained_failed)} legitimacy failures")

        if high_priority:
            action_items.append(f"📋 Review {len(high_priority)} HIGH priority non-portfolio items")

        if action_items:
            for i, item in enumerate(action_items, 1):
                print(f"  {i}. {item}")
        else:
            print("  ✅ No immediate action required - all changes explained and legitimate")

        print()
        print("📁 OUTPUT FILES GENERATED:")
        if ultra_high_priority:
            print("  🚨 PORTFOLIO_IMPACT_ULTRA_HIGH_PRIORITY_*.csv - REVIEW IMMEDIATELY")
            print("  📊 PORTFOLIO_ALERT_*.json - For automated systems")
        print("  📋 Various priority-based CSV files for systematic review")
        print("  📈 validation_summary_*.json - Complete analysis")

        print("=" * 120)

        # Final alert if portfolio impact detected
        if ultra_high_priority:
            print("🚨" * 30)
            print(f"   PORTFOLIO IMPACT DETECTED: {len(ultra_high_priority)} SYMBOLS REQUIRE IMMEDIATE ATTENTION")
            print("🚨" * 30)

        print()