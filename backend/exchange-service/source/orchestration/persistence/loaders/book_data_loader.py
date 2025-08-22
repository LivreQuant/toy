# source/orchestration/persistence/loaders/book_data_loader.py
import os
import json
import logging
from datetime import datetime
from typing import Dict
from decimal import Decimal
import traceback

from source.config import app_config
from source.simulation.managers.account import AccountBalance
from source.simulation.managers.portfolio import Position
from source.simulation.managers.impact import ImpactState
from source.utils.timezone_utils import parse_iso_timestamp
from source.orchestration.persistence.loaders.data_path_resolver import DataPathResolver
from source.simulation.managers.account import AccountManager


class BookDataLoader:
    """Handles loading of book-specific data"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

        current_file = os.path.abspath(__file__)
        # Navigate up from source/orchestration/persistence/loaders/book_data_loader.py to project root
        self.data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))),
            f"data")

        self.path_resolver = DataPathResolver(self.data_dir)

        # CRITICAL FIX: Only check data directory in development mode
        if not app_config.is_production:
            # In development mode, we need the data directory for file access
            if not self.path_resolver.validate_data_directory():
                raise FileNotFoundError(f"Data directory not found: {self.data_dir}")
            self.logger.info(f"🔧 DEVELOPMENT MODE: Data directory validated: {self.data_dir}")
        else:
            # In production mode, we don't need the data directory - using PostgreSQL only
            self.logger.info(f"🚫 PRODUCTION MODE: Skipping data directory validation - using PostgreSQL only")

    async def load_book_data(self, book_id: str, intraday_timestamp_str: str, fallback_date: datetime) -> Dict:
        """Load all book-specific data - environment aware"""
        if app_config.is_production:
            self.logger.info(f"👤 Loading data for book {book_id} from PostgreSQL")
            return await self._load_book_data_from_postgres(book_id, intraday_timestamp_str)
        else:
            self.logger.info(f"👤 Loading data for book {book_id} from files")
            return await self._load_book_data_from_files(book_id, intraday_timestamp_str, fallback_date)

    async def _load_book_data_from_postgres(self, book_id: str, intraday_timestamp_str: str) -> Dict:
        """Load all book-specific data from PostgreSQL (production)"""
        try:
            # Load all data types from PostgreSQL using correct method names
            portfolio_data = await self._load_portfolio_data_from_postgres(book_id, intraday_timestamp_str)
            account_data = await self._load_account_data_from_postgres(book_id, intraday_timestamp_str)
            impact_data = await self._load_impact_data_from_postgres(book_id, intraday_timestamp_str)
            order_data = await self._load_order_data_from_postgres(book_id, intraday_timestamp_str)
            returns_data = await self._load_returns_data_from_postgres(book_id, intraday_timestamp_str)

            book_data = {
                'portfolio': portfolio_data,
                'accounts': account_data,
                'impact': impact_data,
                'orders': order_data,
                'returns': returns_data
            }

            self.logger.info(f"✅ book data loaded from PostgreSQL for {book_id}")
            return book_data

        except Exception as e:
            self.logger.error(f"❌ Error loading book data from PostgreSQL for {book_id}: {e}")
            return self._get_empty_book_data()

    async def _load_book_data_from_files(self, book_id: str, intraday_timestamp_str: str,
                                         fallback_date: datetime) -> Dict:
        """Load all book-specific data from files (development)"""
        try:
            portfolio_data = self._load_portfolio_data_from_files(book_id, intraday_timestamp_str)
            account_data = self._load_account_data_from_files(book_id, intraday_timestamp_str)
            impact_data = self._load_impact_data_from_files(book_id, intraday_timestamp_str)
            order_data = self._load_order_data_from_files(book_id, intraday_timestamp_str)
            returns_data = self._load_returns_data_from_files(book_id, intraday_timestamp_str)

            book_data = {
                'portfolio': portfolio_data,
                'accounts': account_data,
                'impact': impact_data,
                'orders': order_data,
                'returns': returns_data
            }

            self.logger.info(f"✅ book data loaded from files for {book_id}")
            return book_data

        except Exception as e:
            self.logger.error(f"❌ Error loading book data from files for {book_id}: {e}")
            return self._get_empty_book_data()

    def _get_empty_book_data(self) -> Dict:
        """Get empty book data structure"""
        return {
            'portfolio': {},
            'accounts': {},
            'impact': {},
            'orders': {},
            'returns': {}
        }

    # PostgreSQL loading methods (production) - FIXED WITH CORRECT METHOD NAMES
    async def _load_portfolio_data_from_postgres(self, book_id: str, intraday_timestamp_str: str) -> Dict[
        str, Position]:
        """Load portfolio data from PostgreSQL (production)"""
        from source.db.db_manager import db_manager

        try:
            await db_manager.initialize()
            portfolio_data = await db_manager.load_book_portfolio_data(book_id, intraday_timestamp_str)

            self.logger.info(f"✅ Portfolio data loaded from PostgreSQL for {book_id}: {len(portfolio_data)} positions")
            return portfolio_data

        except Exception as e:
            self.logger.error(f"❌ Error loading portfolio data from PostgreSQL for {book_id}: {e}")
            import traceback
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return {}

    async def _load_account_data_from_postgres(self, book_id: str, intraday_timestamp_str: str) -> Dict:
        """Load account data from PostgreSQL (production)"""
        from source.db.db_manager import db_manager

        try:
            await db_manager.initialize()
            account_data = await db_manager.load_book_account_data(book_id, intraday_timestamp_str)

            # CRITICAL FIX: Check if account data is empty and create default accounts if needed
            if not account_data or all(not balances for balances in account_data.values()):
                self.logger.warning(f"⚠️ No account data found for {book_id} at {intraday_timestamp_str}")
                # Create default account structure with USD balance
                default_accounts = self._create_default_account_data()
                self.logger.info(f"✅ Created default account data for {book_id}")
                return default_accounts

            self.logger.info(f"✅ Account data loaded from PostgreSQL for {book_id}")
            return account_data

        except Exception as e:
            self.logger.error(f"❌ Error loading account data from PostgreSQL for {book_id}: {e}")
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            # Return default account data on error
            return self._create_default_account_data()

    def _create_default_account_data(self) -> Dict:
        """Create default account data structure with initial USD balance"""
        # Create default USD balance
        default_balance = AccountBalance(
            currency='USD',
            amount=Decimal('1000000.00')  # 1M USD starting balance
        )

        # Create accounts structure with guaranteed 'balance' key
        accounts = {
            'balance': {'USD': default_balance},
            'cash': {},
            'margin': {},
            'settled': {},
            'unsettled': {}
        }

        self.logger.info("✅ Created default account structure with 1M USD balance")
        return accounts

    async def _load_impact_data_from_postgres(self, book_id: str, intraday_timestamp_str: str) -> Dict[
        str, ImpactState]:
        """Load impact data from PostgreSQL (production)"""
        from source.db.db_manager import db_manager

        try:
            await db_manager.initialize()
            impact_data = await db_manager.load_book_impact_data(book_id, intraday_timestamp_str)

            self.logger.info(f"✅ Impact data loaded from PostgreSQL for {book_id}: {len(impact_data)} symbols")
            return impact_data

        except Exception as e:
            self.logger.error(f"❌ Error loading impact data from PostgreSQL for {book_id}: {e}")
            return {}

    async def _load_order_data_from_postgres(self, book_id: str, intraday_timestamp_str: str) -> Dict:
        """Load order data from PostgreSQL (production)"""
        from source.db.db_manager import db_manager

        try:
            await db_manager.initialize()
            order_data_list = await db_manager.load_book_order_data(book_id, intraday_timestamp_str)

            # Convert list to dict with order_id as key (if needed)
            if isinstance(order_data_list, list):
                order_data_dict = {}
                for order_record in order_data_list:
                    order_id = order_record.get('order_id', '')
                    if order_id:
                        order_data_dict[order_id] = order_record
                order_data = order_data_dict
            else:
                order_data = order_data_list

            self.logger.info(f"✅ Order data loaded from PostgreSQL for {book_id}: {len(order_data)} orders")
            return order_data

        except Exception as e:
            self.logger.error(f"❌ Error loading order data from PostgreSQL for {book_id}: {e}")
            return {}

    async def _load_returns_data_from_postgres(self, book_id: str, intraday_timestamp_str: str) -> Dict:
        """Load returns data from PostgreSQL (production)"""
        from source.db.db_manager import db_manager

        try:
            await db_manager.initialize()
            returns_data = await db_manager.load_book_return_data(book_id, intraday_timestamp_str)

            self.logger.info(f"✅ Returns data loaded from PostgreSQL for {book_id}: {len(returns_data)} entries")
            return returns_data

        except Exception as e:
            self.logger.error(f"❌ Error loading returns data from PostgreSQL for {book_id}: {e}")
            return {}

    # File loading methods (development) - Keep existing implementations
    def _load_portfolio_data_from_files(self, book_id: str, intraday_timestamp_str: str) -> Dict[str, Position]:
        """Load portfolio data from JSON files (development)"""
        file_path = self.path_resolver.get_portfolio_file_path(book_id, intraday_timestamp_str)

        if not self.path_resolver.validate_file_exists(file_path, is_critical=False):
            self.logger.warning(f"⚠️ Portfolio file not found for {book_id}: {file_path}")
            return {}

        try:
            with open(file_path, 'r') as f:
                portfolio_raw = json.load(f)

            portfolio = {}
            for symbol, pos_data in portfolio_raw.items():
                position = Position(
                    symbol=pos_data['symbol'],
                    quantity=float(pos_data['quantity']),
                    target_quantity=float(pos_data['target_quantity']),
                    avg_price=float(pos_data['avg_price']),
                    mtm_value=float(pos_data['mtm_value']),
                    currency=pos_data['currency'],
                    sod_realized_pnl=float(pos_data.get('sod_realized_pnl', 0)),
                    itd_realized_pnl=float(pos_data.get('itd_realized_pnl', 0)),
                    realized_pnl=float(pos_data.get('realized_pnl', 0)),
                    unrealized_pnl=float(pos_data.get('unrealized_pnl', 0))
                )
                portfolio[symbol] = position

            self.logger.info(f"✅ Portfolio data loaded for {book_id}: {len(portfolio)} positions")
            return portfolio

        except Exception as e:
            self.logger.error(f"❌ Error loading portfolio data for {book_id}: {e}")
            return {}

    def _load_account_data_from_files(self, book_id: str, intraday_timestamp_str: str) -> Dict:
        """Load account data from JSON files (development)"""
        file_path = self.path_resolver.get_account_file_path(book_id, intraday_timestamp_str)

        if not self.path_resolver.validate_file_exists(file_path, is_critical=False):
            self.logger.warning(f"⚠️ Account file not found for {book_id}: {file_path}")
            return self._create_default_account_data()

        try:
            with open(file_path, 'r') as f:
                account_data = json.load(f)

            # Initialize account structure
            accounts = {balance_type: {} for balance_type in AccountManager.VALID_TYPES}

            # Process 'balances' array
            for balance_data in account_data.get('balances', []):
                balance_type = balance_data['type']
                currency = balance_data['currency']
                amount = Decimal(str(balance_data['amount']))

                if balance_type in accounts:
                    accounts[balance_type][currency] = AccountBalance(
                        currency=currency,
                        amount=amount
                    )

            total_balances = sum(len(balances) for balances in accounts.values())
            self.logger.info(f"✅ Account data loaded for {book_id}: {total_balances} balances")
            return accounts

        except Exception as e:
            self.logger.error(f"❌ Error loading account data for {book_id}: {e}")
            return self._create_default_account_data()

    def _load_impact_data_from_files(self, book_id: str, intraday_timestamp_str: str) -> Dict[str, ImpactState]:
        """Load impact data from JSON files (development)"""
        file_path = self.path_resolver.get_impact_file_path(book_id, intraday_timestamp_str)

        if not self.path_resolver.validate_file_exists(file_path, is_critical=False):
            self.logger.warning(f"⚠️ Impact file not found for {book_id}: {file_path}")
            return {}

        try:
            with open(file_path, 'r') as f:
                impact_raw = json.load(f)

            impact_data = {}
            for symbol, impact_info in impact_raw.items():
                impact_state = ImpactState(
                    symbol=impact_info['symbol'],
                    current_impact=Decimal(str(impact_info['current_impact'])),
                    decay_rate=Decimal(str(impact_info['decay_rate'])),
                    last_update=parse_iso_timestamp(impact_info['last_update'])
                )
                impact_data[symbol] = impact_state

            self.logger.info(f"✅ Impact data loaded for {book_id}: {len(impact_data)} symbols")
            return impact_data

        except Exception as e:
            self.logger.error(f"❌ Error loading impact data for {book_id}: {e}")
            return {}

    def _load_order_data_from_files(self, book_id: str, intraday_timestamp_str: str) -> Dict:
        """Load order data from JSON files (development)"""
        file_path = self.path_resolver.get_order_file_path(book_id, intraday_timestamp_str)

        if not self.path_resolver.validate_file_exists(file_path, is_critical=False):
            self.logger.warning(f"⚠️ Order file not found for {book_id}: {file_path}")
            return {}

        try:
            with open(file_path, 'r') as f:
                order_data = json.load(f)

            self.logger.info(f"✅ Order data loaded for {book_id}: {len(order_data)} orders")
            return order_data

        except Exception as e:
            self.logger.error(f"❌ Error loading order data for {book_id}: {e}")
            return {}

    def _load_returns_data_from_files(self, book_id: str, intraday_timestamp_str: str) -> Dict:
        """Load returns data from JSON files (development)"""
        file_path = self.path_resolver.get_returns_file_path(book_id, intraday_timestamp_str)

        if not self.path_resolver.validate_file_exists(file_path, is_critical=False):
            self.logger.warning(f"⚠️ Returns file not found for {book_id}: {file_path}")
            return {}

        try:
            with open(file_path, 'r') as f:
                returns_data = json.load(f)

            self.logger.info(f"✅ Returns data loaded for {book_id}: {len(returns_data)} entries")
            return returns_data

        except Exception as e:
            self.logger.error(f"❌ Error loading returns data for {book_id}: {e}")
            return {}