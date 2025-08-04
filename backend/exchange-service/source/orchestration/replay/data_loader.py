# source/orchestration/replay/data_loader.py
import os
import json
import csv
import logging
import asyncio
import threading
from datetime import datetime
from typing import Optional, List
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor

from source.simulation.managers.equity import EquityBar
from source.simulation.managers.fx import FXRate
from source.config import app_config


class DataLoader:
    """Environment-aware data loader with proper async/threading isolation"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        current_file = os.path.abspath(__file__)
        self.data_directory = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file)))),
            f"data")
        
        # Thread-local storage for database connections
        self._thread_local = threading.local()
        # Executor for database operations
        self._db_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="DataLoader-DB")
        
        self.logger.info(f"🔧 DataLoader initialized - Production mode: {app_config.is_production}")

    def _get_thread_db_manager(self):
        """Get or create thread-local database manager"""
        if not hasattr(self._thread_local, 'db_manager'):
            from source.db.db_manager import DatabaseManager
            self._thread_local.db_manager = DatabaseManager()
            self._thread_local.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._thread_local.loop)
            
            # Initialize in the thread's event loop
            self._thread_local.loop.run_until_complete(
                self._thread_local.db_manager.initialize()
            )
            
        return self._thread_local.db_manager, self._thread_local.loop

    def _load_equity_data_for_timestamp(self, timestamp: datetime) -> List[EquityBar]:
        """Load equity data for specific market timestamp - Environment aware with proper async handling"""
        if app_config.is_production:
            self.logger.debug(f"🔄 PRODUCTION MODE: Loading equity data for {timestamp} from PostgreSQL")
            return self._load_equity_data_from_postgres_threadsafe(timestamp)
        else:
            self.logger.debug(f"🔄 DEVELOPMENT MODE: Loading equity data for {timestamp} from files")
            return self._load_equity_data_from_files(timestamp)

    def _load_equity_data_from_postgres_threadsafe(self, timestamp: datetime) -> List[EquityBar]:
        """Load equity data from PostgreSQL using thread isolation"""
        def _db_operation():
            try:
                db_manager, loop = self._get_thread_db_manager()
                timestamp_str = timestamp.strftime('%Y%m%d_%H%M')
                
                equity_data = loop.run_until_complete(
                    db_manager.load_equity_data(timestamp_str)
                )
                
                equity_bars = []
                for equity_dict in equity_data:
                    equity_bar = EquityBar(
                        symbol=equity_dict['symbol'],
                        timestamp=timestamp.isoformat(),
                        currency=equity_dict.get('currency', 'USD'),
                        open=float(equity_dict.get('open', equity_dict.get('close', 100.0))),
                        high=float(equity_dict.get('high', equity_dict.get('close', 100.0))),
                        low=float(equity_dict.get('low', equity_dict.get('close', 100.0))),
                        close=float(equity_dict.get('close', equity_dict.get('close', 100.0))),
                        volume=int(equity_dict.get('volume', equity_dict.get('last_volume', 0))),
                        count=int(equity_dict.get('count', 0)),
                        vwap=float(equity_dict.get('vwap', equity_dict.get('close', 100.0))),
                        vwas=float(equity_dict.get('vwas', 0.0)),
                        vwav=float(equity_dict.get('vwav', 0.0))
                    )
                    equity_bars.append(equity_bar)
                
                self.logger.debug(f"✅ Loaded {len(equity_bars)} equity bars from PostgreSQL for {timestamp_str}")
                return equity_bars
                
            except Exception as e:
                self.logger.error(f"❌ Error loading equity data from PostgreSQL for {timestamp}: {e}")
                return []

        try:
            future = self._db_executor.submit(_db_operation)
            return future.result(timeout=30)
        except Exception as e:
            self.logger.error(f"❌ Error in threaded equity data load: {e}")
            return []

    def _load_equity_data_from_files(self, timestamp: datetime) -> List[EquityBar]:
        """Load equity data from files (development) - supports both CSV and JSON formats"""
        timestamp_str = timestamp.strftime('%Y%m%d_%H%M')

        # Try CSV format first (bin snap files)
        csv_file_path = os.path.join(self.data_directory, "equity", f"{timestamp_str}.csv")
        if os.path.exists(csv_file_path):
            return self._load_equity_from_csv(csv_file_path, timestamp)

        # Try JSON format (backfill files)
        json_file_path = os.path.join(self.data_directory, "equity_data", f"{timestamp_str}.json")
        if os.path.exists(json_file_path):
            return self._load_equity_from_json(json_file_path, timestamp)

        self.logger.debug(f"No equity data file found for: {timestamp_str}")
        return []

    def _load_fx_data_for_timestamp(self, timestamp: datetime) -> Optional[List[FXRate]]:
        """Load FX data for specific market timestamp - Environment aware with proper async handling"""
        if app_config.is_production:
            self.logger.debug(f"🔄 PRODUCTION MODE: Loading FX data for {timestamp} from PostgreSQL")
            return self._load_fx_data_from_postgres_threadsafe(timestamp)
        else:
            self.logger.debug(f"🔄 DEVELOPMENT MODE: Loading FX data for {timestamp} from files")
            return self._load_fx_data_from_files(timestamp)

    def _load_fx_data_from_postgres_threadsafe(self, timestamp: datetime) -> Optional[List[FXRate]]:
        """Load FX data from PostgreSQL using thread isolation"""
        def _db_operation():
            try:
                # Get thread-local database manager and event loop
                db_manager, loop = self._get_thread_db_manager()
                
                timestamp_str = timestamp.strftime('%Y%m%d_%H%M')
                
                # Run async operation in thread's event loop
                fx_data = loop.run_until_complete(
                    db_manager.load_fx_data(timestamp_str)
                )
                
                # Convert database dictionaries to FXRate objects
                fx_rates = []
                for fx_dict in fx_data:
                    # Handle both dict and record types
                    if hasattr(fx_dict, 'from_currency'):
                        # Database record object
                        fx_rate = FXRate(
                            from_currency=fx_dict.from_currency,
                            to_currency=fx_dict.to_currency,
                            rate=fx_dict.rate
                        )
                    else:
                        # Dictionary
                        fx_rate = FXRate(
                            from_currency=fx_dict['from_currency'],
                            to_currency=fx_dict['to_currency'],
                            rate=fx_dict['rate']
                        )
                    fx_rates.append(fx_rate)
                
                self.logger.debug(f"✅ Loaded {len(fx_rates)} FX rates from PostgreSQL for {timestamp_str}")
                return fx_rates
                
            except Exception as e:
                self.logger.error(f"❌ Error loading FX data from PostgreSQL for {timestamp}: {e}")
                return []

        try:
            # Run database operation in dedicated thread
            future = self._db_executor.submit(_db_operation)
            return future.result(timeout=30)
        except Exception as e:
            self.logger.error(f"❌ Error in threaded FX data load: {e}")
            return []

    def _load_fx_data_from_files(self, timestamp: datetime) -> Optional[List[FXRate]]:
        """Load FX data from files (development) - supports both CSV and JSON formats"""
        timestamp_str = timestamp.strftime('%Y%m%d_%H%M')

        csv_file_path = os.path.join(self.data_directory, "fx", f"{timestamp_str}.csv")
        if os.path.exists(csv_file_path):
            return self._load_fx_from_csv(csv_file_path)

        json_file_path = os.path.join(self.data_directory, "fx", f"{timestamp_str}.json")
        if os.path.exists(json_file_path):
            return self._load_fx_from_json(json_file_path)

        self.logger.debug(f"No FX data file found for: {timestamp_str}")
        return None

    def _load_equity_from_csv(self, csv_file_path: str, timestamp: datetime) -> List[EquityBar]:
        """Load equity data from CSV file"""
        equity_bars = []
        try:
            with open(csv_file_path, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    equity_bar = EquityBar(
                        symbol=row['symbol'],
                        timestamp=timestamp.isoformat(),
                        currency=row.get('currency', 'USD'),
                        open=float(row.get('open', row.get('close', 100.0))),
                        high=float(row.get('high', row.get('close', 100.0))),
                        low=float(row.get('low', row.get('close', 100.0))),
                        close=float(row.get('close', row.get('close', 100.0))),
                        volume=int(row.get('volume', row.get('last_volume', 0))),
                        count=int(row.get('count', 0)),
                        vwap=float(row.get('vwap', row.get('close', 100.0))),
                        vwas=float(row.get('vwas', 0.0)),
                        vwav=float(row.get('vwav', 0.0))
                    )
                    equity_bars.append(equity_bar)

            self.logger.debug(f"✅ Loaded {len(equity_bars)} equity bars from CSV: {csv_file_path}")
            return equity_bars

        except Exception as e:
            self.logger.error(f"❌ Error loading equity data from CSV {csv_file_path}: {e}")
            return []

    def _load_equity_from_json(self, json_file_path: str, timestamp: datetime) -> List[EquityBar]:
        """Load equity data from JSON file"""
        try:
            with open(json_file_path, 'r') as jsonfile:
                data = json.load(jsonfile)

            equity_bars = []
            for equity_dict in data:
                equity_bar = EquityBar(
                    symbol=equity_dict['symbol'],
                    timestamp=timestamp.isoformat(),
                    currency=equity_dict.get('currency', 'USD'),
                    open=float(equity_dict.get('open', equity_dict.get('close', 100.0))),
                    high=float(equity_dict.get('high', equity_dict.get('close', 100.0))),
                    low=float(equity_dict.get('low', equity_dict.get('close', 100.0))),
                    close=float(equity_dict.get('close', equity_dict.get('close', 100.0))),
                    volume=int(equity_dict.get('volume', equity_dict.get('last_volume', 0))),
                    count=int(equity_dict.get('count', 0)),
                    vwap=float(equity_dict.get('vwap', equity_dict.get('close', 100.0))),
                    vwas=float(equity_dict.get('vwas', 0.0)),
                    vwav=float(equity_dict.get('vwav', 0.0))
                )
                equity_bars.append(equity_bar)

            self.logger.debug(f"✅ Loaded {len(equity_bars)} equity bars from JSON: {json_file_path}")
            return equity_bars

        except Exception as e:
            self.logger.error(f"❌ Error loading equity data from JSON {json_file_path}: {e}")
            return []

    def _load_fx_from_csv(self, csv_file_path: str) -> List[FXRate]:
        """Load FX data from CSV file"""
        fx_rates = []
        try:
            with open(csv_file_path, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    fx_rate = FXRate(
                        from_currency=row['from_currency'],
                        to_currency=row['to_currency'],
                        rate=Decimal(str(row['rate'])),
                        timestamp=row['timestamp']
                    )
                    fx_rates.append(fx_rate)

            self.logger.debug(f"✅ Loaded {len(fx_rates)} FX rates from CSV: {csv_file_path}")
            return fx_rates

        except Exception as e:
            self.logger.error(f"❌ Error loading FX data from CSV {csv_file_path}: {e}")
            return []

    def _load_fx_from_json(self, json_file_path: str) -> List[FXRate]:
        """Load FX data from JSON file"""
        try:
            with open(json_file_path, 'r') as jsonfile:
                data = json.load(jsonfile)

            fx_rates = []
            for fx_dict in data:
                fx_rate = FXRate(
                    from_currency=fx_dict['from_currency'],
                    to_currency=fx_dict['to_currency'],
                    rate=Decimal(str(fx_dict['rate'])),
                    timestamp=fx_dict['timestamp']
                )
                fx_rates.append(fx_rate)

            self.logger.debug(f"✅ Loaded {len(fx_rates)} FX rates from JSON: {json_file_path}")
            return fx_rates

        except Exception as e:
            self.logger.error(f"❌ Error loading FX data from JSON {json_file_path}: {e}")
            return []