# src/generator/market_data_generator.py
import random
import logging
import time
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class MarketDataGenerator:
    """
    Generates simulated market data for a list of symbols.
    This mimics minute bar data from a real market data feed.
    """
    
    def __init__(self, symbols: List[str]):
        """
        Initialize the market data generator.
        
        Args:
            symbols: List of ticker symbols to generate data for
        """
        self.symbols = symbols
        self.prices: Dict[str, float] = {}
        self.last_update_time = 0
        
        # Initialize with realistic prices for common stocks
        self._initialize_prices()
        
        logger.info(f"Market data generator initialized with {len(symbols)} symbols")
    
    def _initialize_prices(self):
        """Initialize price data with realistic values for symbols"""
        # Sample realistic prices for common stocks
        base_prices = {
            "AAPL": 190.0,  # Apple
            "MSFT": 420.0,  # Microsoft
            "GOOGL": 160.0,  # Google
            "AMZN": 180.0,  # Amazon
            "TSLA": 200.0,  # Tesla
            "FB": 490.0,     # Meta (Facebook)
            "NVDA": 930.0,  # NVIDIA
            "BRK.A": 620000.0,  # Berkshire Hathaway
            "JPM": 195.0,  # JP Morgan
            "V": 280.0,  # Visa
        }
        
        # Set initial prices based on base prices or random if not in the list
        for symbol in self.symbols:
            if symbol in base_prices:
                self.prices[symbol] = base_prices[symbol]
            else:
                # For unknown symbols, generate a random price between $5 and $500
                self.prices[symbol] = random.uniform(5.0, 500.0)
    
    def update_prices(self):
        """
        Update prices for all symbols with realistic market movements.
        Called on each update interval to simulate price changes.
        """
        self.last_update_time = time.time()
        
        for symbol in self.symbols:
            current_price = self.prices[symbol]
            
            # Higher-priced stocks typically have larger absolute price movements
            # but smaller percentage movements
            price_volatility = 0.002  # Base 0.2% volatility for minute bar
            
            # Add some randomness to volatility based on the symbol
            symbol_volatility = sum(ord(c) for c in symbol) % 10 / 1000  # 0-0.9% additional volatility
            
            # Calculate percentage change with slight positive bias (reflecting long-term market trends)
            percent_change = random.normalvariate(0.0001, price_volatility + symbol_volatility)
            
            # Apply the price change
            new_price = current_price * (1 + percent_change)
            
            # Ensure price doesn't go below $1.00
            self.prices[symbol] = max(1.00, round(new_price, 2))
        
        logger.debug(f"Updated prices for {len(self.symbols)} symbols")
    
    def get_market_data(self) -> List[Dict[str, Any]]:
        """
        Generate market data records with OHLCV and additional fields.
        
        Returns:
            List of market data dictionaries
        """
        market_data = []
        current_time = int(time.time() * 1000)  # Milliseconds
        
        for symbol in self.symbols:
            price = self.prices[symbol]
            
            # Generate realistic OHLC data
            open_price = round(price * (1 - random.uniform(0, 0.005)), 2)
            high_price = round(price * (1 + random.uniform(0, 0.005)), 2)
            low_price = round(price * (1 - random.uniform(0, 0.005)), 2)
            close_price = price
            
            # Generate volume and trade count
            volume = random.randint(1000, 100000)
            trade_count = random.randint(10, 1000)
            
            # Calculate VWAP (Volume Weighted Average Price)
            vwap = round((open_price + high_price + low_price + close_price) / 4, 2)
            
            market_data.append({
                'symbol': symbol,
                'timestamp': current_time,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': volume,
                'trade_count': trade_count,
                'vwap': vwap
            })
        
        return market_data
    
    def get_price(self, symbol: str) -> float:
        """
        Get the current price for a specific symbol.
        
        Args:
            symbol: The ticker symbol
            
        Returns:
            Current price or 0.0 if symbol not found
        """
        return self.prices.get(symbol, 0.0)
    
    def get_time_since_update(self) -> float:
        """
        Get time in seconds since the last price update.
        
        Returns:
            Seconds since last update
        """
        return time.time() - self.last_update_time