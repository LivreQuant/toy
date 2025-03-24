import time
import uuid
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"

class OrderStatus(str, Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"

@dataclass
class Order:
    session_id: str
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType
    
    # Optional fields
    price: Optional[float] = None
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_id: Optional[str] = None
    status: OrderStatus = OrderStatus.NEW
    filled_quantity: float = 0
    average_price: float = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error_message: Optional[str] = None
    
    def to_dict(self):
        """Convert to dictionary representation"""
        return {
            'order_id': self.order_id,
            'session_id': self.session_id,
            'symbol': self.symbol,
            'side': self.side.value if isinstance(self.side, OrderSide) else self.side,
            'quantity': self.quantity,
            'price': self.price,
            'order_type': self.order_type.value if isinstance(self.order_type, OrderType) else self.order_type,
            'request_id': self.request_id,
            'status': self.status.value if isinstance(self.status, OrderStatus) else self.status,
            'filled_quantity': self.filled_quantity,
            'average_price': self.average_price,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'error_message': self.error_message
        }