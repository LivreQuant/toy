#!/usr/bin/env python3
"""
Portfolio and corporate action data models
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from decimal import Decimal
from abc import ABC


@dataclass
class Position:
    """Represents a portfolio position"""
    symbol: str
    quantity: Decimal


@dataclass
class Account:
    """Represents account balances"""
    currency: str
    balance: Decimal


@dataclass
class UserPortfolio:
    """Represents a user's portfolio and accounts"""
    user_id: str
    positions: List[Position]
    accounts: Dict[str, Decimal]  # currency -> balance


@dataclass
class CorporateAction(ABC):
    """Base class for corporate actions"""
    symbol: str
    action_type: str
    effective_date: str
    source: str


@dataclass
class SymbolChange(CorporateAction):
    """Symbol change corporate action"""
    old_symbol: str
    new_symbol: str


@dataclass
class Delisting(CorporateAction):
    """Delisting corporate action"""
    currency: str
    account: str
    value_per_share: Decimal


@dataclass
class MergerComponent:
    """Component of a merger (cash or stock)"""
    type: str  # 'cash' or 'stock'
    parent: str  # symbol or account name
    currency: Optional[str]
    value: Decimal


@dataclass
class Merger(CorporateAction):
    """Merger corporate action"""
    components: List[MergerComponent]


@dataclass
class StockSplit(CorporateAction):
    """Stock split corporate action"""
    split_ratio: Decimal


@dataclass
class StockDividend(CorporateAction):
    """Stock dividend corporate action"""
    dividend_ratio: Decimal
    payable_date: Optional[str] = None


@dataclass
class CashDividend(CorporateAction):
    """Cash dividend corporate action"""
    dividend_per_share: Decimal
    currency: str
    account: str
    payable_date: Optional[str] = None


@dataclass
class PortfolioUpdate:
    """Result of applying a corporate action"""
    original_position: Position
    action: CorporateAction
    new_positions: List[Position]
    cash_adjustments: Dict[str, Decimal]


@dataclass
class UserUpdate:
    """Result of applying corporate actions to a user"""
    user_id: str
    original_portfolio: UserPortfolio
    updates: List[PortfolioUpdate]
    final_positions: Dict[str, Decimal]  # symbol -> quantity
    final_accounts: Dict[str, Decimal]  # currency -> balance


@dataclass
class UnexplainedPosition:
    """Position that couldn't be explained by corporate actions"""
    position: Position
    reason: str
