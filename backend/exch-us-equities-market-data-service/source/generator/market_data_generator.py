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
    Uses current UTC time and converts to market timezone to determine market hours.
    Always provides data - live during market hours, last available data otherwise.
    Kubernetes runs 24/7/365.
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
        
        # Time management - use current UTC time, no start_time from config
        self.time_increment = timedelta(minutes=market_config.get("time_increment_minutes", 1))
        
        # Market hours logic - store last market prices and data
        self.last_market_prices: Dict[str, float] = self.current_prices.copy()
        self.last_market_fx_rates: Dict[tuple, float] = self.current_fx_rates.copy()
        self.last_market_equity_data: List[Dict[str, Any]] = []
        self.last_market_fx_data: List[Dict[str, Any]] = []
        
        # Market hours configuration from JSON or defaults
        market_hours = market_config.get("market_hours", {})
        self.pre_market_start_hour = market_hours.get("pre_market_start", 4)      # 4:00 AM
        self.pre_market_start_minute = market_hours.get("pre_market_start_min", 0)
        self.market_open_hour = market_hours.get("market_open", 9)               # 9:30 AM
        self.market_open_minute = market_hours.get("market_open_min", 30)
        self.market_close_hour = market_hours.get("market_close", 16)            # 4:00 PM
        self.market_close_minute = market_hours.get("market_close_min", 0)
        self.after_hours_end_hour = market_hours.get("after_hours_end", 20)      # 8:00 PM
        self.after_hours_end_minute = market_hours.get("after_hours_end_min", 0)
        
        logger.info(f"Controlled market data generator initialized for 24/7/365 operation")
        logger.info(f"Market timezone: {self.timezone_name}")
        logger.info(f"Kubernetes runs continuously - UTC time converted to {self.timezone_name} for market hours")
        logger.info(f"Market hours (in {self.timezone_name}): Pre-market {self.pre_market_start_hour:02d}:{self.pre_market_start_minute:02d}-{self.market_open_hour:02d}:{self.market_open_minute:02d}, Regular {self.market_open_hour:02d}:{self.market_open_minute:02d}-{self.market_close_hour:02d}:{self.market_close_minute:02d}, After-hours {self.market_close_hour:02d}:{self.market_close_minute:02d}-{self.after_hours_end_hour:02d}:{self.after_hours_end_minute:02d}")
        logger.info(f"Symbols: {list(self.current_prices.keys())}")
        logger.info(f"FX pairs: {list(self.current_fx_rates.keys())}")
        logger.info(f"Data policy: Live prices during market hours, last available prices otherwise (weekends, holidays, closed hours)")

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

    def _get_current_market_time(self) -> datetime:
        """Get current UTC time converted to market timezone"""
        utc_now = datetime.utcnow()
        
        if self.timezone is None:
            return utc_now
            
        if TIMEZONE_MODULE == "zoneinfo":
            utc_aware = utc_now.replace(tzinfo=ZoneInfo('UTC'))
            return utc_aware.astimezone(self.timezone)
        elif TIMEZONE_MODULE == "pytz":
            utc_aware = pytz.utc.localize(utc_now)
            return utc_aware.astimezone(self.timezone)
        else:
            return utc_now

    def is_market_hours(self, dt: Optional[datetime] = None) -> tuple[bool, str]:
        """
        Check if the given datetime (or current market time) is within market hours.
        Uses current UTC time converted to market timezone.
        Weekends and holidays automatically return closed status.
        
        Returns:
            Tuple of (is_trading_hours, market_status)
            market_status can be: 'pre_market', 'regular_hours', 'after_hours', 'closed'
        """
        if dt is None:
            dt = self._get_current_market_time()
        elif dt.tzinfo is None and self.timezone:
            # If naive datetime provided, assume it's in market timezone
            if TIMEZONE_MODULE == "zoneinfo":
                dt = dt.replace(tzinfo=self.timezone)
            elif TIMEZONE_MODULE == "pytz":
                dt = self.timezone.localize(dt)
        elif dt.tzinfo is not None and self.timezone:
            # Convert to market timezone
            dt = dt.astimezone(self.timezone)
        
        # Check if it's a weekend (Saturday=5, Sunday=6)
        if dt.weekday() >= 5:
            return False, 'closed_weekend'
        
        # Convert times to minutes for easier comparison
        current_minutes = dt.hour * 60 + dt.minute
        
        pre_market_start_minutes = self.pre_market_start_hour * 60 + self.pre_market_start_minute
        market_open_minutes = self.market_open_hour * 60 + self.market_open_minute
        market_close_minutes = self.market_close_hour * 60 + self.market_close_minute
        after_hours_end_minutes = self.after_hours_end_hour * 60 + self.after_hours_end_minute
        
        if pre_market_start_minutes <= current_minutes < market_open_minutes:
            return True, 'pre_market'
        elif market_open_minutes <= current_minutes < market_close_minutes:
            return True, 'regular_hours'
        elif market_close_minutes <= current_minutes < after_hours_end_minutes:
            return True, 'after_hours'
        else:
            return False, 'closed_hours'

    def update_prices(self):
        """
        Update prices based on controlled increments from configuration.
        Only updates prices during market hours (weekdays + trading hours).
        Always provides last market data when closed (weekends, holidays, off-hours).
        Uses current UTC time converted to market timezone.
        """
        current_market_time = self._get_current_market_time()
        is_trading, market_status = self.is_market_hours(current_market_time)
        
        if is_trading:
            # Update equity prices during market hours
            for symbol in self.current_prices:
                config = self.equity_config[symbol]
                price_change = config["price_change_per_minute"]
                self.current_prices[symbol] = round(self.current_prices[symbol] + price_change, 2)
            
            # Update FX rates during market hours  
            for key in self.current_fx_rates:
                config = self.fx_config[key]
                rate_change = config["rate_change_per_minute"]
                self.current_fx_rates[key] = round(self.current_fx_rates[key] + rate_change, 4)
            
            # Store these as the last market prices
            self.last_market_prices = self.current_prices.copy()
            self.last_market_fx_rates = self.current_fx_rates.copy()
            
            logger.debug(f"Updated prices during {market_status} at {current_market_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        else:
            # Outside market hours (weekends, holidays, closed hours) - use last market prices
            reason = "weekend" if "weekend" in market_status else "closed hours"
            logger.debug(f"Market closed ({reason}) - using last available prices at {current_market_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    def get_market_data(self) -> Dict[str, Any]:
        """
        Generate controlled market data records for database storage.
        Returns live data during market hours, last market data otherwise.
        Always returns data - Kubernetes runs 24/7/365.
        Uses current UTC time converted to market timezone.
        
        Returns:
            Dictionary containing equity and fx data arrays
        """
        current_market_time = self._get_current_market_time()
        utc_time = datetime.utcnow()
        timestamp_ms = int(utc_time.timestamp() * 1000)
        is_trading, market_status = self.is_market_hours(current_market_time)
        
        # Use current prices if in market hours, last market prices if closed
        prices_to_use = self.current_prices if is_trading else self.last_market_prices
        fx_rates_to_use = self.current_fx_rates if is_trading else self.last_market_fx_rates
        
        # Generate equity data
        equity_data = []
        for symbol in prices_to_use:
            config = self.equity_config[symbol]
            price = prices_to_use[symbol]
            
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
                'volume': config["base_volume"] if is_trading else 0,  # No volume when closed
                'trade_count': config["trade_count"] if is_trading else 0,  # No trades when closed
                'currency': config["currency"],
                'exchange': config["exchange"]
            })
        
        # Generate FX data
        fx_data = []
        for (from_curr, to_curr), rate in fx_rates_to_use.items():
            fx_data.append({
                'from_currency': from_curr,
                'to_currency': to_curr,
                'rate': rate,
                'timestamp': utc_time.isoformat() + 'Z'
            })
        
        # Store last market data when trading
        if is_trading:
            self.last_market_equity_data = equity_data.copy()
            self.last_market_fx_data = fx_data.copy()
        
        return {
            'timestamp': timestamp_ms,
            'bin_time': current_market_time.strftime('%H%M'),
            'current_time': utc_time,
            'market_time': current_market_time,
            'equity': equity_data,
            'fx': fx_data,
            'timezone': self.timezone_name,
            'market_status': market_status,
            'is_trading_hours': is_trading,
            'weekday': current_market_time.strftime('%A'),
            'is_weekend': current_market_time.weekday() >= 5
        }

    def get_current_time(self) -> datetime:
        """Get the current UTC time"""
        return datetime.utcnow()

    def get_current_market_time(self) -> datetime:
        """Get the current time in market timezone"""
        return self._get_current_market_time()

    def get_symbols(self) -> List[str]:
        """Get list of equity symbols"""
        return list(self.current_prices.keys())

    def get_fx_pairs(self) -> List[tuple]:
        """Get list of FX pairs"""
        return list(self.current_fx_rates.keys())

    def get_current_prices(self) -> Dict[str, float]:
        """Get current prices for all symbols (or last market prices if closed)"""
        is_trading, _ = self.is_market_hours()
        return self.current_prices.copy() if is_trading else self.last_market_prices.copy()

    def get_current_fx_rates(self) -> Dict[tuple, float]:
        """Get current FX rates for all pairs (or last market rates if closed)"""
        is_trading, _ = self.is_market_hours()
        return self.current_fx_rates.copy() if is_trading else self.last_market_fx_rates.copy()

    def get_market_status(self) -> tuple[bool, str]:
        """Get current market status using current UTC time"""
        return self.is_market_hours()