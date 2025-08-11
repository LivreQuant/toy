# source/db/db_manager.py
import asyncpg
import logging
from typing import Optional
from source.config import app_config


class DatabaseManager:
    """Main database manager that coordinates all table-specific managers"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.pool: Optional[asyncpg.Pool] = None
        self._initialized = False

        # Initialize table-specific managers
        self._init_table_managers()

    def _init_table_managers(self):
        """Initialize all table-specific managers"""
        from source.db.managers.metadata import MetadataManager
        from source.db.managers.users import UsersManager
        from source.db.managers.universe_data import UniverseDataManager
        from source.db.managers.risk_factor_data import RiskFactorDataManager
        from source.db.managers.equity_data import EquityDataManager
        from source.db.managers.fx_data import FxDataManager
        from source.db.managers.portfolio_data import PortfolioDataManager
        from source.db.managers.account_data import AccountDataManager
        from source.db.managers.impact_data import ImpactDataManager
        from source.db.managers.order_data import OrderDataManager
        from source.db.managers.return_data import ReturnDataManager
        from source.db.managers.trade_data import TradeDataManager
        from source.db.managers.cash_flow_data import CashFlowDataManager
        from source.db.managers.user_operational_parameters import UserOperationalParametersManager

        # Initialize managers (they will receive the pool when it's created)
        self.metadata = MetadataManager(self)
        self.users = UsersManager(self)
        self.universe_data = UniverseDataManager(self)
        self.risk_factor_data = RiskFactorDataManager(self)

        self.equity_data = EquityDataManager(self)
        self.fx_data = FxDataManager(self)

        self.portfolio_data = PortfolioDataManager(self)
        self.account_data = AccountDataManager(self)
        self.impact_data = ImpactDataManager(self)
        self.order_data = OrderDataManager(self)
        self.return_data = ReturnDataManager(self)
        self.trade_data = TradeDataManager(self)

        self.cash_flow_data = CashFlowDataManager(self)

        # New parameter managers
        self.user_operational_parameters = UserOperationalParametersManager(self)

    async def initialize(self):
        """Initialize database connection pool"""
        if self._initialized:
            return

        if not app_config.is_production:
            self.logger.info("🔄 Database manager initialized for non-production (no connections)")
            self._initialized = True
            return

        try:
            self.pool = await asyncpg.create_pool(
                app_config.database.connection_string,
                min_size=app_config.database.min_connections,
                max_size=app_config.database.max_connections,
                command_timeout=60
            )
            self.logger.info("✅ Database connection pool initialized")
            self._initialized = True
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize database pool: {e}")
            raise

    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            self._initialized = False
            self.logger.info("✅ Database connection pool closed")

    @property
    def connected(self) -> bool:
        """Check if database is connected"""
        return self.pool is not None and not self.pool._closed

    # Legacy compatibility methods - delegate to appropriate table managers
    async def load_exchange_metadata(self, exch_id: str = None):
        """Load exchange metadata - delegates to metadata manager"""
        return await self.metadata.load_exchange_metadata(exch_id)

    async def load_risk_factor_data(self, timestamp_str: str):
        """Load risk factor data - delegates to risk factor manager"""
        return await self.risk_factor_data.load_user_data(timestamp_str)

    async def load_universe_data(self, timestamp_str: str):
        """Load universe data - delegates to universe manager"""
        return await self.universe_data.load_universe_data(timestamp_str)

    async def load_equity_data(self, timestamp_str: str):
        """Load equity data - delegates to equity manager"""
        return await self.equity_data.load_equity_data(timestamp_str)

    async def load_fx_data(self, timestamp_str: str):
        """Load FX data - delegates to fx manager"""
        return await self.fx_data.load_fx_data(timestamp_str)

    # USER SPECIFIC

    async def load_users_for_exchange(self, exch_id: str):
        """Load users for exchange - delegates to users manager"""
        return await self.users.load_users_for_exchange(exch_id)

    async def load_user_portfolio_data(self, user_id: str, timestamp_str: str):
        """Load user portfolio data - delegates to portfolio manager"""
        return await self.portfolio_data.load_user_data(user_id, timestamp_str)

    async def load_user_account_data(self, user_id: str, timestamp_str: str):
        """Load user account data - delegates to account manager"""
        return await self.account_data.load_user_data(user_id, timestamp_str)

    async def load_user_impact_data(self, user_id: str, timestamp_str: str):
        """Load user impact data - delegates to impact manager"""
        return await self.impact_data.load_user_data(user_id, timestamp_str)

    async def load_user_order_data(self, user_id: str, timestamp_str: str):
        """Load user orders data - delegates to order manager"""
        return await self.order_data.load_user_data(user_id, timestamp_str)

    async def load_user_return_data(self, user_id: str, timestamp_str: str):
        """Load user returns data - delegates to return manager"""
        return await self.return_data.load_user_data(user_id, timestamp_str)

    # Add convenience methods
    async def load_user_operational_parameters(self, user_id: str):
        """Load PM operational parameters for user"""
        return await self.user_operational_parameters.load_parameters_for_user(user_id)

    async def insert_simulation_data(self, table_name: str, data, user_id: str, timestamp):
        """Insert simulation data - routes to appropriate table manager"""
        table_manager_map = {
            'account_data': self.account_data,
            'cash_flow_data': self.cash_flow_data,
            'impact_data': self.impact_data,
            'order_data': self.order_data,
            'portfolio_data': self.portfolio_data,
            'return_data': self.return_data,
            'risk_factor_data': self.risk_factor_data,
            'trade_data': self.trade_data,
        }

        if table_name in table_manager_map:
            return await table_manager_map[table_name].insert_simulation_data(data, user_id, timestamp)
        else:
            self.logger.error(f"❌ Unknown table name: {table_name}")
            return 0


# Global instance
db_manager = DatabaseManager()