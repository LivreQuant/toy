from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import time
import uuid
import json

from source.models.enums import OrderSide, OrderType, OrderStatus


@dataclass
class Order:
    """Order model representing a trading order"""
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
    simulator_id: Optional[str] = None  # Added field for simulator ID
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
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

        # Convert string enum values to actual enums if needed
        if isinstance(self.side, str):
            self.side = OrderSide(self.side)
        if isinstance(self.order_type, str):
            self.order_type = OrderType(self.order_type)
        if isinstance(self.status, str):
            self.status = OrderStatus(self.status)

    def to_dict(self) -> Dict[str, Any]:
        """Convert order to dictionary for serialization"""
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

    def to_json(self) -> str:
        """Convert order to JSON string"""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Order':
        """Create order from dictionary"""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'Order':
        """Create order from JSON string"""
        return cls.from_dict(json.loads(json_str))