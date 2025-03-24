# source/models/order.py
from enum import Enum
from dataclasses import dataclass
from typing import Optional
import time
import uuid
import json

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
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType
    user_id: str
    session_id: str
    
    # Optional fields
    price: Optional[float] = None
    order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.NEW
    filled_quantity: float = 0
    avg_price: float = 0
    simulator_id: Optional[str] = None
    created_at: float = 0
    updated_at: float = 0
    request_id: Optional[str] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        # Generate order_id if not provided
        if not self.order_id:
            self.order_id = str(uuid.uuid4())
        
        # Set timestamps if not provided
        current_time = time.time()
        if not self.created_at:
            self.created_at = current_time
        if not self.updated_at:
            self.updated_at = current_time
    
    def to_dict(self):
        """Convert order to dictionary for JSON serialization"""
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value if isinstance(self.side, OrderSide) else self.side,
            "quantity": self.quantity,
            "price": self.price,
            "order_type": self.order_type.value if isinstance(self.order_type, OrderType) else self.order_type,
            "status": self.status.value if isinstance(self.status, OrderStatus) else self.status,
            "filled_quantity": self.filled_quantity,
            "avg_price": self.avg_price,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "simulator_id": self.simulator_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "request_id": self.request_id,
            "error_message": self.error_message
        }
    
    def to_json(self):
        """Convert order to JSON string"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data):
        """Create order from dictionary"""
        # Convert string enum values to actual enums
        if isinstance(data.get('side'), str):
            data['side'] = OrderSide(data['side'])
        if isinstance(data.get('order_type'), str):
            data['order_type'] = OrderType(data['order_type'])
        if isinstance(data.get('status'), str):
            data['status'] = OrderStatus(data['status'])
        
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str):
        """Create order from JSON string"""
        return cls.from_dict(json.loads(json_str))