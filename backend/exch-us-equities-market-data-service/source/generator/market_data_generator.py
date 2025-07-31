# source/generator/market_data_generator.py
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Timezone handling
try:
    from zoneinfo import ZoneInfo
    TIMEZONE_MODULE = "zoneinfo"
except ImportError:
    try:
        import pytz
        TIMEZONE_MODULE = "pytz"
    except ImportError:
        TIMEZONE_MODULE = None

logger = logging.getLogger(__name__)

class ControlledMarketDataGenerator:
    """
    Generates controlled market data based on JSON configuration.
    All data goes directly to PostgreSQL - no CSV output.
    """
    
    def __init__(self, market_config: Dict[str, Any]):
        """
        Initialize the controlled market data generator.
        
        Args:
            market_config: Configuration dictionary loaded from JSON
        """
        self.config = market_config
        self.timezone_name = market_config.get("timezone", "America/New_York")
        self.timezone = self._get_timezone(self.timezone_name)
        
        # Initialize current prices and FX rates from config
        self.current_prices: Dict[str, float] = {}
        self.equity_config: Dict[str, Dict] = {}
        
        for equity in market_config["equity"]:
            symbol = equity["symbol"]
            self.current_prices[symbol] = equity["starting_price"]
            self.equity_config[symbol] = equity
        
        self.current_fx_rates: Dict[tuple, float] = {}
        self.fx_config: Dict[tuple, Dict] = {}
        
        for fx in market_config["fx"]:
            key = (fx["from_currency"], fx["to_currency"])
            self.current_fx_rates[key] = fx["starting_rate"]
            self.fx_config[key] = fx
        
        # Time management
        start_time_str = market_config["start_time"]
        if 'T' in start_time_str:
            naive_start_time = datetime.fromisoformat(start_time_str.replace('Z', ''))
        else:
            naive_start_time = datetime.fromisoformat(start_time_str + 'T00:00:00')
            
        self.current_time = self._make_timezone_aware(naive_start_time)
        self.time_increment = timedelta(minutes=market_config["time_increment_minutes"])
        
        logger.info(f"Controlled market data generator initialized")
        logger.info(f"Timezone: {self.timezone_name}")
        logger.info(f"Start time: {self.current_time.isoformat()}")
        logger.info(f"Symbols: {list(self.current_prices.keys())}")
        logger.info(f"FX pairs: {list(self.current_fx_rates.keys())}")
        logger.info(f"Database-only output - no CSV files")

    def _get_timezone(self, timezone_name: str):
        """Get timezone object"""
        if TIMEZONE_MODULE == "zoneinfo":
            try:
                return ZoneInfo(timezone_name)
            except Exception as e:
                logger.error(f"Failed to create zoneinfo timezone {timezone_name}: {e}")
                return None
        elif TIMEZONE_MODULE == "pytz":
            try:
                return pytz.timezone(timezone_name)
            except Exception as e:
                logger.error(f"Failed to create pytz timezone {timezone_name}: {e}")
                return None
        else:
            logger.warning("No timezone module available")
            return None

    def _make_timezone_aware(self, dt: datetime) -> datetime:
        """Make datetime timezone-aware"""
        if self.timezone is None:
            return dt

        if dt.tzinfo is not None:
            return dt.astimezone(self.timezone)

        if TIMEZONE_MODULE == "zoneinfo":
            return dt.replace(tzinfo=self.timezone)
        elif TIMEZONE_MODULE == "pytz":
            return self.timezone.localize(dt)
        else:
            return dt

    def update_prices(self):
        """
        Update prices based on controlled increments from configuration.
        This replaces random price movements with predictable changes.
        """
        # Update equity prices
        for symbol in self.current_prices:
            config = self.equity_config[symbol]
            price_change = config["price_change_per_minute"]
            self.current_prices[symbol] = round(self.current_prices[symbol] + price_change, 2)
        
        # Update FX rates
        for key in self.current_fx_rates:
            config = self.fx_config[key]
            rate_change = config["rate_change_per_minute"]
            self.current_fx_rates[key] = round(self.current_fx_rates[key] + rate_change, 4)
        
        # Advance time
        self.current_time += self.time_increment
        
        logger.debug(f"Updated controlled prices and advanced time to {self.current_time}")

    def get_market_data(self) -> Dict[str, Any]:
        """
        Generate controlled market data records for database storage.
        
        Returns:
            Dictionary containing equity and fx data arrays
        """
        timestamp_ms = int(self.current_time.timestamp() * 1000)
        
        # Generate equity data
        equity_data = []
        for symbol in self.current_prices:
            config = self.equity_config[symbol]
            price = self.current_prices[symbol]
            
            # Generate controlled OHLC with minimal spread
            open_price = round(price, 2)
            high_price = round(price + 0.01, 2)
            low_price = round(price - 0.01, 2) 
            close_price = round(price, 2)
            
            equity_data.append({
                'symbol': symbol,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'vwap': round(price, 2),
                'vwas': round(config["vwas"], 4),
                'vwav': round(config["vwav"], 4),
                'volume': config["base_volume"],
                'trade_count': config["trade_count"],
                'currency': config["currency"],
                'exchange': config["exchange"]
            })
        
        # Generate FX data
        fx_data = []
        for (from_curr, to_curr), rate in self.current_fx_rates.items():
            fx_data.append({
                'from_currency': from_curr,
                'to_currency': to_curr,
                'rate': rate,
                'timestamp': self.current_time.isoformat()
            })
        
        return {
            'timestamp': timestamp_ms,
            'bin_time': self.current_time.strftime('%H%M'),
            'current_time': self.current_time,
            'equity': equity_data,
            'fx': fx_data,
            'timezone': self.timezone_name
        }

    def get_current_time(self) -> datetime:
        """Get the current simulated time"""
        return self.current_time

    def get_symbols(self) -> List[str]:
        """Get list of equity symbols"""
        return list(self.current_prices.keys())

    def get_fx_pairs(self) -> List[tuple]:
        """Get list of FX pairs"""
        return list(self.current_fx_rates.keys())

    def get_current_prices(self) -> Dict[str, float]:
        """Get current prices for all symbols"""
        return self.current_prices.copy()

    def get_current_fx_rates(self) -> Dict[tuple, float]:
        """Get current FX rates for all pairs"""
        return self.current_fx_rates.copy()