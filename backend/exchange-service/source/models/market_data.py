from dataclasses import dataclass
from typing import Dict, List, Any, Optional

@dataclass
class MarketData:
    """Market data for a single symbol"""
    symbol: str
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    last_price: float
    last_size: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'symbol': self.symbol,
            'bid': self.bid,
            'ask': self.ask,
            'bid_size': self.bid_size,
            'ask_size': self.ask_size,
            'last_price': self.last_price,
            'last_size': self.last_size
        }