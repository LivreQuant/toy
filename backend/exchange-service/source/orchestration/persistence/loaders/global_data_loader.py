# source/orchestration/persistence/loaders/global_data_loader.py
import os
import json
import logging
import asyncio
from typing import Dict, List
from decimal import Decimal

from source.config import app_config
from source.simulation.managers.fx import FXRate
from source.orchestration.persistence.loaders.data_path_resolver import DataPathResolver


class GlobalDataLoader:
    """Handles loading of global data shared across all users"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        current_file = os.path.abspath(__file__)
        # Navigate up from source/orchestration/persistence/loaders/global_data_loader.py to project root
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

    async def load_global_data(self, daily_timestamp_str: str, intraday_timestamp_str: str) -> Dict:
        """Load all global data components - NOW ASYNC"""
        self.logger.info("🌍 Loading global data components...")

        global_data = {
            'universe': await self.load_universe_data(daily_timestamp_str),
            'risk_factors': await self.load_risk_factor_data(daily_timestamp_str),
            'equity': await self.load_equity_data(intraday_timestamp_str),
            'fx': await self.load_fx_data(intraday_timestamp_str)
        }

        self.logger.info("✅ Global data loading complete")
        return global_data

    async def load_universe_data(self, daily_timestamp_str: str) -> Dict[str, Dict]:
        """Load universe data - NOW ASYNC"""
        if app_config.is_production:
            self.logger.info("🔄 PRODUCTION MODE: Loading universe data from PostgreSQL")
            return await self._load_universe_data_from_postgres(daily_timestamp_str)
        else:
            self.logger.info("🔄 DEVELOPMENT MODE: Loading universe data from JSON files")
            return self._load_universe_data_from_files(daily_timestamp_str)

    async def load_risk_factor_data(self, daily_timestamp_str: str) -> List[Dict]:
        """Load risk factor data - NOW ASYNC"""
        if app_config.is_production:
            self.logger.info("🔄 PRODUCTION MODE: Loading risk factor data from PostgreSQL")
            return await self._load_risk_factor_data_from_postgres(daily_timestamp_str)
        else:
            self.logger.info("🔄 DEVELOPMENT MODE: Loading risk factor data from JSON files")
            return self._load_risk_factor_data_from_files(daily_timestamp_str)

    async def load_equity_data(self, intraday_timestamp_str: str) -> List[Dict]:
        """Load equity data - NOW ASYNC"""
        if app_config.is_production:
            self.logger.info("🔄 PRODUCTION MODE: Loading equity data from PostgreSQL")
            return await self._load_equity_data_from_postgres(intraday_timestamp_str)
        else:
            self.logger.info("🔄 DEVELOPMENT MODE: Loading equity data from JSON files")
            return self._load_equity_data_from_files(intraday_timestamp_str)

    async def load_fx_data(self, intraday_timestamp_str: str) -> List[FXRate]:
        """Load FX data - NOW ASYNC"""
        if app_config.is_production:
            self.logger.info("🔄 PRODUCTION MODE: Loading FX data from PostgreSQL")
            return await self._load_fx_data_from_postgres(intraday_timestamp_str)
        else:
            self.logger.info("🔄 DEVELOPMENT MODE: Loading FX data from JSON files")
            return self._load_fx_data_from_files(intraday_timestamp_str)

    def _load_universe_data_from_files(self, daily_timestamp_str: str) -> Dict[str, Dict]:
        """Load universe data from JSON files (development)"""
        file_path = self.path_resolver.get_universe_file_path(daily_timestamp_str)

        self.logger.info(f"🔍 Looking for universe file (daily): {file_path}")
        self.logger.info(f"   File exists: {os.path.exists(file_path)}")

        # Debug: List what files actually exist in the universe directory
        universe_dir = os.path.dirname(file_path)
        if os.path.exists(universe_dir):
            files_in_dir = os.listdir(universe_dir)
            self.logger.info(f"🔍 Files in universe directory: {files_in_dir}")
        else:
            self.logger.error(f"🔍 Universe directory does not exist: {universe_dir}")

        if not self.path_resolver.validate_file_exists(file_path, is_critical=False):
            self.logger.warning(f"⚠️ Universe file not found: {file_path}")
            return {}

        try:
            with open(file_path, 'r') as f:
                universe_data = json.load(f)

            self.logger.info(f"✅ Loaded universe data: {len(universe_data)} symbols")
            return universe_data

        except Exception as e:
            self.logger.error(f"❌ Error loading universe data: {e}")
            return {}

    def _load_risk_factor_data_from_files(self, daily_timestamp_str: str) -> List[Dict]:
        """Load risk factor data from JSON files (development)"""
        file_path = self.path_resolver.get_risk_factor_file_path(daily_timestamp_str)

        self.logger.info(f"🔍 Looking for risk factor file: {file_path}")
        self.logger.info(f"   File exists: {os.path.exists(file_path)}")

        if not self.path_resolver.validate_file_exists(file_path, is_critical=False):
            self.logger.warning(f"⚠️ Risk factor file not found: {file_path}")
            return []

        try:
            with open(file_path, 'r') as f:
                risk_factor_data = json.load(f)

            self.logger.info(f"✅ Risk factor data loaded: {len(risk_factor_data)} items")
            return risk_factor_data

        except Exception as e:
            self.logger.error(f"❌ Error loading risk factor data: {e}")
            return []

    def _load_equity_data_from_files(self, intraday_timestamp_str: str) -> List[Dict]:
        """Load equity data from JSON files (development)"""
        file_path = self.path_resolver.get_equity_file_path(intraday_timestamp_str)

        self.logger.info(f"🔍 Looking for equity file (intraday): {file_path}")
        self.logger.info(f"   File exists: {os.path.exists(file_path)}")

        if not self.path_resolver.validate_file_exists(file_path, is_critical=False):
            self.logger.warning(f"⚠️ Equity file not found: {file_path}")
            return []

        try:
            with open(file_path, 'r') as f:
                equity_data = json.load(f)

            self.logger.info(f"✅ Equity data loaded: {len(equity_data)} items")
            return equity_data

        except Exception as e:
            self.logger.error(f"❌ Error loading equity data: {e}")
            return []

    def _load_fx_data_from_files(self, intraday_timestamp_str: str) -> List[FXRate]:
        """Load FX data from JSON files (development)"""
        file_path = self.path_resolver.get_fx_file_path(intraday_timestamp_str)

        self.logger.info(f"🔍 Looking for FX file (intraday): {file_path}")
        self.logger.info(f"   File exists: {os.path.exists(file_path)}")

        if not self.path_resolver.validate_file_exists(file_path, is_critical=False):
            self.logger.warning(f"⚠️ FX file not found: {file_path}")
            return []

        try:
            with open(file_path, 'r') as f:
                fx_data_raw = json.load(f)

            fx_rates = []
            for item in fx_data_raw:
                fx_rate = FXRate(
                    from_currency=item['base_currency'],
                    to_currency=item['quote_currency'],
                    rate=Decimal(str(item['rate']))
                )
                fx_rates.append(fx_rate)

            self.logger.info(f"✅ FX data loaded: {len(fx_rates)} rates")
            return fx_rates

        except Exception as e:
            self.logger.error(f"❌ Error loading FX data: {e}")
            return []

    # PostgreSQL loading methods
    async def _load_universe_data_from_postgres(self, daily_timestamp_str: str) -> Dict[str, Dict]:
        """Load universe data from PostgreSQL (production)"""
        from source.db.db_manager import db_manager

        try:
            await db_manager.initialize()
            universe_data_list = await db_manager.load_universe_data(daily_timestamp_str)

            # CRITICAL FIX: Convert list of dictionaries to dict with symbol keys
            # This is what UniverseManager and UniverseStateManager expect
            universe_dict = {}
            for item in universe_data_list:
                symbol = item.get('symbol')
                if symbol:
                    universe_dict[symbol] = {
                        'symbol': symbol,
                        'sector': item.get('sector', ''),
                        'industry': item.get('industry', ''),
                        'market_cap': float(item.get('market_cap', 0)),
                        'country': item.get('country', ''),
                        'currency': item.get('currency', 'USD'),
                        'avg_daily_volume': int(item.get('avg_daily_volume', 0)),
                        'beta': float(item.get('beta', 1.0)),
                        'primary_exchange': item.get('primary_exchange', ''),
                        'shares_outstanding': int(item.get('shares_outstanding', 0)),
                        # Add empty structures for optional fields that session service expects
                        'exposures': {},
                        'custom_attributes': {}
                    }

            self.logger.info(f"✅ Universe data loaded from PostgreSQL: {len(universe_dict)} symbols")
            return universe_dict

        except Exception as e:
            self.logger.error(f"❌ Error loading universe data from PostgreSQL: {e}")
            import traceback
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return {}

    async def _load_risk_factor_data_from_postgres(self, daily_timestamp_str: str) -> List[Dict]:
        """Load risk factor data from PostgreSQL (production)"""
        from source.db.db_manager import db_manager

        try:
            await db_manager.initialize()
            risk_factor_data = await db_manager.load_risk_factor_data(daily_timestamp_str)
            self.logger.info(f"✅ Risk factor data loaded from PostgreSQL: {len(risk_factor_data)} items")
            return risk_factor_data
        except Exception as e:
            self.logger.error(f"❌ Error loading risk factor data from PostgreSQL: {e}")
            return []

    async def _load_equity_data_from_postgres(self, intraday_timestamp_str: str) -> List[Dict]:
        """Load equity data from PostgreSQL (production)"""
        from source.db.db_manager import db_manager

        try:
            await db_manager.initialize()
            equity_data = await db_manager.load_equity_data(intraday_timestamp_str)
            self.logger.info(f"✅ Equity data loaded from PostgreSQL: {len(equity_data)} items")
            return equity_data
        except Exception as e:
            self.logger.error(f"❌ Error loading equity data from PostgreSQL: {e}")
            return []

    async def _load_fx_data_from_postgres(self, intraday_timestamp_str: str) -> List[FXRate]:
        """Load FX data from PostgreSQL (production)"""
        from source.db.db_manager import db_manager

        try:
            await db_manager.initialize()
            fx_data = await db_manager.load_fx_data(intraday_timestamp_str)

            self.logger.debug(f"🔍 DEBUG: fx_data type: {type(fx_data)}")
            self.logger.debug(f"🔍 DEBUG: fx_data sample: {fx_data[:2] if fx_data else 'Empty'}")

            fx_rates = []

            # CRITICAL FIX: Handle both list of records AND list of dictionaries
            for item in fx_data:
                try:
                    # If it's a database record (has attributes)
                    if hasattr(item, 'from_currency') and hasattr(item, 'to_currency'):
                        fx_rate = FXRate(
                            from_currency=item.from_currency,
                            to_currency=item.to_currency,
                            rate=item.rate
                        )
                    # If it's a dictionary
                    elif isinstance(item, dict):
                        fx_rate = FXRate(
                            from_currency=item.get('from_currency', ''),
                            to_currency=item.get('to_currency', ''),
                            rate=Decimal(str(item.get('rate', 0)))
                        )
                    else:
                        self.logger.error(f"❌ Unknown FX data item type: {type(item)}, content: {item}")
                        continue

                    fx_rates.append(fx_rate)

                except Exception as item_error:
                    self.logger.error(f"❌ Error processing FX item {item}: {item_error}")
                    continue

            self.logger.info(f"✅ FX data loaded from PostgreSQL: {len(fx_rates)} rates")
            return fx_rates

        except Exception as e:
            self.logger.error(f"❌ Error loading FX data from PostgreSQL: {e}")
            import traceback
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return []

    def get_risk_factor_file_path(self, daily_timestamp: str) -> str:
        """Get path to risk factor file (daily snapshot, JSON format)"""
        return os.path.join(self.data_dir, "risk_factors", f"{daily_timestamp}.json")