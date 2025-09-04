#!/usr/bin/env python3
"""
Enhanced validation result structure with portfolio impact tracking
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class ValidationResult:
    """Enhanced structure to hold validation results with portfolio impact tracking"""
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

    # Additional flags for manual review prioritization
    has_price_data: bool = field(init=False)
    priority_for_review: str = "LOW"  # LOW, MEDIUM, HIGH

    def __post_init__(self):
        """Post-initialization processing"""
        # Determine if has price data
        self.has_price_data = bool(self.al_symbol and self.al_symbol.strip())

        # Set initial priority for manual review (can be overridden by portfolio check)
        if self.portfolio_holding:
            self.priority_for_review = "ULTRA_HIGH"
        elif not self.explained and self.has_price_data:
            self.priority_for_review = "HIGH"
        elif not self.explained:
            self.priority_for_review = "LOW"
