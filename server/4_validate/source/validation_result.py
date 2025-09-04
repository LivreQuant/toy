#!/usr/bin/env python3
"""
Updated validation result structure with enhanced priority logic
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class ValidationResult:
    """Enhanced validation result with portfolio-focused priority assignment"""
    symbol: str
    type: str
    al_symbol: str
    composite_key: str
    change_type: str  # NEW_ENTRY or MISSING_ENTRY
    explanation: str
    explained: bool

    # Corporate action information
    corporate_action_type: Optional[str] = None
    corporate_action_date: Optional[str] = None
    confidence: float = 0.0
    details: Optional[Dict] = None

    # Legitimacy check results
    legitimacy_passed: bool = False
    legitimacy_issues: Optional[str] = None

    # Portfolio impact tracking
    portfolio_holding: bool = False
    portfolio_impact_reason: Optional[str] = None

    # Priority assignment (will be set by PriorityAssigner)
    priority_for_review: str = "LOW"  # ULTRA_HIGH, HIGH, MEDIUM, LOW, EXPLAINED

    # Computed properties
    has_price_data: bool = field(init=False)

    def __post_init__(self):
        """Post-initialization processing"""
        # Determine if has price data (al_symbol indicates tradeable security)
        self.has_price_data = bool(self.al_symbol and self.al_symbol.strip())

    def get_business_impact_description(self) -> str:
        """Get human-readable description of business impact"""
        if self.portfolio_holding:
            if self.change_type == "MISSING_ENTRY":
                return f"Portfolio symbol {self.symbol} missing from master list - immediate investigation required"
            else:
                return f"New portfolio-related symbol {self.symbol} detected - verify legitimacy"

        if self.has_price_data and not self.explained:
            return f"Tradeable symbol {self.symbol} unexplained - operational risk"

        if not self.explained:
            return f"Non-tradeable symbol {self.symbol} unexplained - low priority investigation"

        if self.explained and not self.legitimacy_passed:
            return f"Corporate action for {self.symbol} failed verification - data integrity concern"

        return f"Symbol {self.symbol} properly explained and verified"

    def requires_immediate_action(self) -> bool:
        """Check if this result requires immediate action"""
        return (
                self.portfolio_holding or
                (self.explained and not self.legitimacy_passed and self.portfolio_holding)
        )

    def get_recommended_action(self) -> str:
        """Get recommended action based on result"""
        if self.portfolio_holding and self.change_type == "MISSING_ENTRY":
            return "URGENT: Verify portfolio position status and investigate symbol removal"

        if self.portfolio_holding and not self.explained:
            return "HIGH: Investigate unexplained portfolio-related change"

        if self.explained and not self.legitimacy_passed:
            return "MEDIUM: Verify corporate action legitimacy"

        if self.has_price_data and not self.explained:
            return "LOW-MEDIUM: Research unexplained tradeable symbol change"

        return "LOW: Standard investigation when resources available"