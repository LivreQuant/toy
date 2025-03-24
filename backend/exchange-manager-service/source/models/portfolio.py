from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import time

@dataclass
class Position:
    symbol: str
    quantity: float
    average_cost: float
    market_value: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'average_cost': self.average_cost,
            'market_value': self.market_value
        }

@dataclass
class Portfolio:
    user_id: str
    session_id: str
    cash_balance: float = 100000.0
    positions: Dict[str, Position] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def get_total_value(self) -> float:
        """Calculate total portfolio value (cash + positions)"""
        position_value = sum(pos.market_value for pos in self.positions.values())
        return self.cash_balance + position_value
    
    def has_position(self, symbol: str) -> bool:
        """Check if portfolio has a position in a symbol"""
        return symbol in self.positions
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get a position by symbol"""
        return self.positions.get(symbol)
    
    def update_position_market_value(self, symbol: str, price: float) -> None:
        """Update the market value of a position based on current price"""
        if symbol in self.positions:
            position = self.positions[symbol]
            position.market_value = position.quantity * price
            self.updated_at = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'cash_balance': self.cash_balance,
            'total_value': self.get_total_value(),
            'positions': [pos.to_dict() for pos in self.positions.values()],
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def to_proto_format(self) -> Dict[str, Any]:
        """Convert to format needed for gRPC response"""
        return {
            'cash_balance': self.cash_balance,
            'total_value': self.get_total_value(),
            'positions': [pos.to_dict() for pos in self.positions.values()]
        }