import random
import time
from typing import Dict, List, Optional
from source.models.order import Order
from source.models.enums import OrderSide, OrderType, OrderStatus
from source.core.market_data import MarketDataGenerator

class OrderManager:
    def __init__(self, market_data: MarketDataGenerator):
        self.market_data = market_data
        self.orders: Dict[str, Order] = {}
        self.session_orders: Dict[str, List[str]] = {}

    def submit_order(
        self, 
        session_id: str, 
        symbol: str, 
        side: OrderSide, 
        quantity: float, 
        order_type: OrderType, 
        price: Optional[float] = None
    ) -> Order:
        """Submit a new order with basic execution simulation"""
        order = Order(
            session_id=session_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price
        )

        # Simulate basic order execution
        current_price = self.market_data.prices.get(symbol, 0)
        
        # Market order: immediate execution
        if order_type == OrderType.MARKET:
            executed_qty = quantity
            order.update(executed_qty, current_price)
        
        # Limit order: partial or no execution
        elif order_type == OrderType.LIMIT:
            if (side == OrderSide.BUY and current_price <= price) or \
               (side == OrderSide.SELL and current_price >= price):
                executed_qty = quantity
                order.update(executed_qty, price)
            else:
                order.status = OrderStatus.NEW

        # Store order
        self.orders[order.order_id] = order
        
        if session_id not in self.session_orders:
            self.session_orders[session_id] = []
        self.session_orders[session_id].append(order.order_id)

        return order

    def cancel_order(self, session_id: str, order_id: str) -> bool:
        """Cancel an existing order"""
        order = self.orders.get(order_id)
        
        if not order or order.session_id != session_id:
            return False
        
        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED]:
            return False
        
        order.status = OrderStatus.CANCELED
        order.updated_at = time.time()
        return True

    def get_order_status(self, session_id: str, order_id: str) -> Optional[Order]:
        """Retrieve order status"""
        order = self.orders.get(order_id)
        
        if not order or order.session_id != session_id:
            return None
        
        return order