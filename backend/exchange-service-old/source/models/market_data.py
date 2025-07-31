from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class MarketData:
    """Market data for a single symbol (minute bars)"""
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    trade_count: int = 0
    vwap: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'symbol': self.symbol,
            'open': self.open,
            'high': self.high, 
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'trade_count': self.trade_count,
            'vwap': self.vwap
        }
    