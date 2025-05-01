import time
import uuid
from dataclasses import dataclass, field
from typing import Optional
from source.models.enums import OrderSide, OrderType, OrderStatus


@dataclass
class Order:
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType
    price: Optional[float] = None
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: OrderStatus = OrderStatus.NEW
    filled_quantity: float = 0
    average_price: float = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error_message: Optional[str] = None

    def update(self, filled_quantity: float, average_price: float):
        """Update order status based on execution"""
        self.filled_quantity += filled_quantity
        self.average_price = average_price
        self.updated_at = time.time()

        if self.filled_quantity >= self.quantity:
            self.status = OrderStatus.FILLED
        elif self.filled_quantity > 0:
            self.status = OrderStatus.PARTIALLY_FILLED
