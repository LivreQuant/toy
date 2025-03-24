import random
import time
import logging
from typing import Dict, List, Any

from source.models.market_data import MarketData
from source.utils.metrics import Metrics, timed

logger = logging.getLogger(__name__)
metrics = Metrics()

class MarketDataGenerator:
    """Generates realistic market data for simulation"""
    
    def __init__(self, symbols=None):
        """
        Initialize market data generator
        
        Args:
            symbols: List of symbols to track
        """
        self.symbols = symbols or ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
        self.prices = {
            "AAPL": 175.0,
            "MSFT": 350.0,
            "GOOGL": 140.0,
            "AMZN": 130.0,
            "TSLA": 200.0
        }
        # Add any missing symbols with random prices
        for symbol in self.symbols:
            if symbol not in self.prices:
                self.prices[symbol] = random.uniform(50.0, 500.0)
        
        # Track volatility for each symbol
        self.volatility = {symbol: random.uniform(0.005, 0.02) for symbol in self.symbols}
        
        # Metrics
        metrics.set_gauge("market_data_symbols_count", len(self.symbols))

    @timed("market_data_update")
    def update_prices(self):
        """Update prices with random movements"""
        for symbol in self.symbols:
            current_price = self.prices[symbol]
            volatility = self.volatility[symbol]
            
            # Random price movement based on volatility
            price_change = current_price * (random.random() * volatility * 2 - volatility)
            new_price = max(0.01, current_price + price_change)
            self.prices[symbol] = new_price
            
            # Occasionally adjust volatility
            if random.random() < 0.05:  # 5% chance
                self.volatility[symbol] = max(0.001, min(0.05, self.volatility[symbol] * (0.8 + random.random() * 0.4)))

    def get_price(self, symbol: str) -> float:
        """Get current price for a symbol"""
        return self.prices.get(symbol, 0.0)

    def get_market_data(self, symbols=None) -> List[Dict[str, Any]]:
        """Generate market data for the specified symbols"""
        market_data = []
        for symbol in (symbols or self.symbols):
            if symbol in self.prices:
                price = self.prices[symbol]
                # Create small random spread
                spread = price * self.volatility[symbol] * 0.5
                bid = price - spread
                ask = price + spread

                market_data.append({
                    'symbol': symbol,
                    'bid': bid,
                    'ask': ask,
                    'bid_size': random.randint(100, 1000),
                    'ask_size': random.randint(100, 1000),
                    'last_price': price,
                    'last_size': random.randint(10, 100)
                })

        return market_data