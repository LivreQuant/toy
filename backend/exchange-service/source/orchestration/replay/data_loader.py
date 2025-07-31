# source/orchestration/replay/data_loader.py
"""
Data loading functionality for equity and FX market data
"""

import os
import csv
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from source.config import app_config
from source.simulation.managers.equity import EquityBar
from source.simulation.managers.fx import FXRate


class DataLoader:
    """Handles loading of market data from various file formats"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

        current_file = os.path.abspath(__file__)
        # Navigate up from source/orchestration/replay/data_loader.py to project root
        self.data_directory = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file)))),
            f"data")

    def load_missing_data(self, gap_start: datetime, gap_end: datetime) -> List[
        Tuple[datetime, List[EquityBar], Optional[List[FXRate]]]]:
        """
        Load missing equity and FX data from the data directory for the MARKET gap period.
        Returns list of (market_timestamp, equity_bars, fx) tuples.
        Supports both CSV/JSON (dev) and PostgreSQL (prod) formats.
        """
        missing_data = []

        self.logger.info(f"🔍 LOADING MISSING MARKET DATA:")
        self.logger.info(f"   Environment: {app_config.environment}")
        self.logger.info(f"   From: {gap_start}")
        self.logger.info(f"   To: {gap_end}")

        # Calculate total minutes to process
        total_minutes = int((gap_end - gap_start).total_seconds() / 60) + 1
        self.logger.info(f"   Total minutes to process: {total_minutes}")

        if total_minutes > 500:  # More than ~8 hours
            self.logger.warning(f"⚠️ Large backfill detected ({total_minutes} minutes) - this may take some time")

        # Generate list of missing timestamps (minute by minute)
        current = gap_start
        processed_count = 0
        found_count = 0

        while current <= gap_end:
            try:
                # Try to load data for this timestamp (environment-aware)
                equity_bars = self._load_equity_data_for_timestamp(current)
                fx_rates = self._load_fx_data_for_timestamp(current)

                if equity_bars:  # Only add if we have equity data
                    missing_data.append((current, equity_bars, fx_rates))
                    found_count += 1
                    if found_count <= 5:  # Log first few entries
                        self.logger.info(
                            f"✅ Loaded market data for {current}: {len(equity_bars)} bars, {len(fx_rates) if fx_rates else 0} FX rates")
                    elif found_count % 50 == 0:  # Log every 50th entry
                        self.logger.info(f"✅ Progress: {found_count} market data points loaded...")

                processed_count += 1

                # Progress logging for large gaps
                if processed_count % 100 == 0:
                    progress_pct = (processed_count / total_minutes) * 100
                    self.logger.info(f"📊 Backfill progress: {processed_count}/{total_minutes} ({progress_pct:.1f}%)")

            except Exception as e:
                self.logger.error(f"❌ Error loading market data for {current}: {e}")

            current += timedelta(minutes=1)

        self.logger.info(f"📊 MISSING MARKET DATA SUMMARY:")
        self.logger.info(f"   Total timestamps processed: {processed_count}")
        self.logger.info(f"   Market data points found: {found_count}")
        self.logger.info(
            f"   Success rate: {(found_count / processed_count) * 100:.1f}%" if processed_count > 0 else "0%")
        self.logger.info(f"   Market data range: {gap_start} to {gap_end}")

        return missing_data

    def _load_equity_data_for_timestamp(self, timestamp: datetime) -> List[EquityBar]:
        """Load equity data for specific market timestamp - Environment aware"""

        # CHECK FOR PRODUCTION MODE FIRST
        if app_config.is_production:
            self.logger.debug(f"🔄 PRODUCTION MODE: Loading equity data for {timestamp} from PostgreSQL")
            return self._load_equity_data_from_postgres(timestamp)
        else:
            self.logger.debug(f"🔄 DEVELOPMENT MODE: Loading equity data for {timestamp} from files")
            return self._load_equity_data_from_files(timestamp)

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

    def _load_equity_data_from_postgres(self, timestamp: datetime) -> List[EquityBar]:
        """Load equity data from PostgreSQL (production)"""
        from source.db.db_manager import db_manager

        try:
            timestamp_str = timestamp.strftime('%Y%m%d_%H%M')

            # Fixed async handling
            async def load_equity_async():
                await db_manager.initialize()
                return await db_manager.load_equity_data(timestamp_str)

            # Use proper async execution
            try:
                # Try to get existing event loop
                loop = asyncio.get_running_loop()
                # If we're in a running loop, we need to use run_in_executor
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, load_equity_async())
                    equity_data = future.result()
            except RuntimeError:
                # No running loop, safe to use asyncio.run
                equity_data = asyncio.run(load_equity_async())

            # Convert from List[Dict] format to List[EquityBar]
            equity_bars = []
            for equity_dict in equity_data:
                equity_bar = EquityBar(
                    symbol=equity_dict['symbol'],
                    timestamp=timestamp.isoformat(),
                    currency=equity_dict.get('currency', 'USD'),
                    open=float(equity_dict.get('open', equity_dict.get('last_price', 100.0))),
                    high=float(equity_dict.get('high', equity_dict.get('last_price', 100.0))),
                    low=float(equity_dict.get('low', equity_dict.get('last_price', 100.0))),
                    close=float(equity_dict.get('close', equity_dict.get('last_price', 100.0))),
                    volume=int(equity_dict.get('volume', equity_dict.get('last_volume', 0))),
                    count=int(equity_dict.get('count', 0)),
                    vwap=float(equity_dict.get('vwap', equity_dict.get('last_price', 100.0))),
                    vwas=float(equity_dict.get('vwas', 0.0)),
                    vwav=float(equity_dict.get('vwav', 0.0))
                )
                equity_bars.append(equity_bar)

            self.logger.debug(f"✅ Loaded {len(equity_bars)} equity bars from PostgreSQL for {timestamp_str}")
            return equity_bars

        except Exception as e:
            self.logger.error(f"❌ Error loading equity data from PostgreSQL for {timestamp}: {e}")
            return []

    def _load_fx_data_for_timestamp(self, timestamp: datetime) -> Optional[List[FXRate]]:
        """Load FX data for specific market timestamp - Environment aware"""

        # CHECK FOR PRODUCTION MODE FIRST
        if app_config.is_production:
            self.logger.debug(f"🔄 PRODUCTION MODE: Loading FX data for {timestamp} from PostgreSQL")
            return self._load_fx_data_from_postgres(timestamp)
        else:
            self.logger.debug(f"🔄 DEVELOPMENT MODE: Loading FX data for {timestamp} from files")
            return self._load_fx_data_from_files(timestamp)

    def _load_fx_data_from_files(self, timestamp: datetime) -> Optional[List[FXRate]]:
        """Load FX data from files (development) - supports both CSV and JSON formats"""
        timestamp_str = timestamp.strftime('%Y%m%d_%H%M')

        # Try CSV format first (bin snap files)
        csv_file_path = os.path.join(self.data_directory, "fx", f"{timestamp_str}.csv")
        if os.path.exists(csv_file_path):
            return self._load_fx_from_csv(csv_file_path)

        # Try JSON format (backfill files)
        json_file_path = os.path.join(self.data_directory, "fx", f"{timestamp_str}.json")
        if os.path.exists(json_file_path):
            return self._load_fx_from_json(json_file_path)

        self.logger.debug(f"No FX data file found for: {timestamp_str}")
        return None

    def _load_fx_data_from_postgres(self, timestamp: datetime) -> Optional[List[FXRate]]:
        """Load FX data from PostgreSQL (production)"""
        from source.db.db_manager import db_manager

        try:
            timestamp_str = timestamp.strftime('%Y%m%d_%H%M')

            # Fixed async handling
            async def load_fx_async():
                await db_manager.initialize()
                return await db_manager.load_fx_data(timestamp_str)

            # Use proper async execution
            try:
                # Try to get existing event loop
                loop = asyncio.get_running_loop()
                # If we're in a running loop, we need to use run_in_executor
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, load_fx_async())
                    fx_data = future.result()
            except RuntimeError:
                # No running loop, safe to use asyncio.run
                fx_data = asyncio.run(load_fx_async())

            self.logger.debug(f"✅ Loaded {len(fx_data)} FX rates from PostgreSQL for {timestamp_str}")
            return fx_data

        except Exception as e:
            self.logger.error(f"❌ Error loading FX data from PostgreSQL for {timestamp}: {e}")
            return None

    def _load_equity_from_csv(self, file_path: str, timestamp: datetime) -> List[EquityBar]:
        """Load equity data from CSV file (bin snap format)"""
        try:
            equity_bars = []
            with open(file_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    equity_bar = EquityBar(
                        symbol=row['symbol'],
                        timestamp=timestamp.isoformat(),
                        currency=row.get('currency', 'USD'),
                        open=float(row['open']),
                        high=float(row['high']),
                        low=float(row['low']),
                        close=float(row['close']),
                        volume=int(row['volume']),
                        count=int(row.get('count', 1)),
                        vwap=float(row.get('vwap', row['close'])),
                        vwas=float(row.get('vwas', '0')),
                        vwav=float(row.get('vwav', '0'))
                    )
                    equity_bars.append(equity_bar)

            self.logger.debug(f"✅ Loaded {len(equity_bars)} equity bars from CSV: {file_path}")
            return equity_bars

        except Exception as e:
            self.logger.error(f"❌ Error loading equity data from CSV {file_path}: {e}")
            return []

    def _load_equity_from_json(self, file_path: str, timestamp: datetime) -> List[EquityBar]:
        """Load equity data from JSON file (backfill format)"""
        try:
            with open(file_path, 'r') as f:
                equity_data = json.load(f)

            equity_bars = []
            for data in equity_data.get('data', []):
                equity_bar = EquityBar(
                    symbol=data['symbol'],
                    timestamp=timestamp.isoformat(),
                    currency=data.get('currency', 'USD'),
                    open=float(data.get('open', 100.0)),
                    high=float(data.get('high', 100.0)),
                    low=float(data.get('low', 100.0)),
                    close=float(data.get('close', 100.0)),
                    volume=int(data.get('volume', 0)),
                    count=int(data.get('count', 0)),
                    vwap=float(data.get('vwap', 100.0)),
                    vwas=float(data.get('vwas', 100.0)),
                    vwav=float(data.get('vwav', 100.0))
                )
                equity_bars.append(equity_bar)

            self.logger.debug(f"✅ Loaded {len(equity_bars)} equity bars from JSON: {file_path}")
            return equity_bars

        except Exception as e:
            self.logger.error(f"❌ Error loading equity data from JSON {file_path}: {e}")
            return []

    def _load_fx_from_csv(self, file_path: str) -> List[FXRate]:
        """Load FX data from CSV file (bin snap format)"""
        try:
            fx_rates = []
            with open(file_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    fx_rate = FXRate(
                        from_currency=row['from_currency'],
                        to_currency=row['to_currency'],
                        rate=float(row['rate'])
                    )
                    fx_rates.append(fx_rate)

            self.logger.debug(f"✅ Loaded {len(fx_rates)} FX rates from CSV: {file_path}")
            return fx_rates

        except Exception as e:
            self.logger.error(f"❌ Error loading FX data from CSV {file_path}: {e}")
            return []

    def _load_fx_from_json(self, file_path: str) -> List[FXRate]:
        """Load FX data from JSON file (backfill format)"""
        try:
            with open(file_path, 'r') as f:
                fx_data = json.load(f)

            fx_rates = []
            for rate_data in fx_data.get('rates', []):
                fx_rate = FXRate(
                    from_currency=rate_data['from_currency'],
                    to_currency=rate_data['to_currency'],
                    rate=float(rate_data['rate'])
                )
                fx_rates.append(fx_rate)

            self.logger.debug(f"✅ Loaded {len(fx_rates)} FX rates from JSON: {file_path}")
            return fx_rates

        except Exception as e:
            self.logger.error(f"❌ Error loading FX data from JSON {file_path}: {e}")
            return []