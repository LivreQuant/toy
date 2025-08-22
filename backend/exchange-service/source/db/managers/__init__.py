# source/db/managers/__init__.py
"""
Database table managers package.

This package contains individual managers for each database table,
providing a clean separation of concerns and better maintainability.
"""

from .base_manager import BaseTableManager
from .metadata import MetadataManager
from .books import BooksManager
from .book_operational_parameters import BookOperationalParametersManager
from .universe_data import UniverseDataManager
from .risk_factor_data import RiskFactorDataManager
from .equity_data import EquityDataManager
from .fx_data import FxDataManager
from .portfolio_data import PortfolioDataManager
from .account_data import AccountDataManager
from .impact_data import ImpactDataManager
from .order_data import OrderDataManager
from .return_data import ReturnDataManager
from .trade_data import TradeDataManager

__all__ = [
    'BaseTableManager',
    'MetadataManager',
    'BooksManager',
    'BookOperationalParametersManager',
    'UniverseDataManager',
    'RiskFactorDataManager',
    'EquityDataManager',
    'FxDataManager',
    'PortfolioDataManager',
    'AccountDataManager',
    'ImpactDataManager',
    'OrderDataManager',
    'ReturnDataManager',
    'TradeDataManager'
]