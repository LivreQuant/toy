import random
import time
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class MarketDataGenerator:
    def __init__(self, symbols=None):
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
    
    def update_prices(self):
        """Update prices with random movements"""
        for symbol in self.symbols:
            current_price = self.prices[symbol]
            # Random price movement -0.5% to +0.5%
            price_change = current_price * (random.random() * 0.01 - 0.005)
            new_price = max(0.01, current_price + price_change)
            self.prices[symbol] = new_price
    
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
                bid = price - random.random() * 0.02
                ask = price + random.random() * 0.02
                
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