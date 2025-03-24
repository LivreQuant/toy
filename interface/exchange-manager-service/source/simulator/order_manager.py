import time
import uuid
import random
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class OrderManager:
    def __init__(self, portfolio_manager, market_data_generator):
        self.portfolio_manager = portfolio_manager
        self.market_data = market_data_generator
        self.orders = {}  # order_id -> order_info
        self.session_orders = {}  # session_id -> list of order_ids
    
    def create_random_order(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Create a random order for a session"""
        # Get active symbols for this session
        symbols = self.market_data.symbols
        
        # 10% chance of generating a trade
        if random.random() > 0.1:
            return None
            
        # Create random order
        symbol = random.choice(symbols)
        side = random.choice(["BUY", "SELL"])
        quantity = random.randint(1, 10) * 10  # 10, 20, ..., 100
        price = self.market_data.get_price(symbol)
        
        # Create order object
        order_id = str(uuid.uuid4())
        
        order = {
            'order_id': order_id,
            'session_id': session_id,
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'price': price,
            'status': 'NEW',
            'filled_quantity': 0,
            'average_price': 0,
            'created_at': time.time()
        }
        
        # Store order
        self.orders[order_id] = order
        
        # Add to session orders
        if session_id not in self.session_orders:
            self.session_orders[session_id] = []
        self.session_orders[session_id].append(order_id)
        
        # Execute the order (simplified - immediate fill)
        self._execute_order(order_id)
        
        return order
    
    def _execute_order(self, order_id: str):
        """Execute an order"""
        if order_id not in self.orders:
            return
            
        order = self.orders[order_id]
        session_id = order['session_id']
        symbol = order['symbol']
        side = order['side']
        quantity = order['quantity']
        price = order['price']
        
        # Execute in portfolio
        success = self.portfolio_manager.execute_trade(
            session_id, symbol, side, quantity, price)
        
        if success:
            # Update order status
            order['status'] = 'FILLED'
            order['filled_quantity'] = quantity
            order['average_price'] = price
            order['updated_at'] = time.time()
            logger.info(f"Order {order_id} filled: {quantity} {symbol} @ {price}")
        else:
            # Mark as rejected
            order['status'] = 'REJECTED'
            order['updated_at'] = time.time()
            logger.warning(f"Order {order_id} rejected")
    
    def get_recent_orders(self, session_id: str, max_count: int = 10) -> List[Dict[str, Any]]:
        """Get recent orders for a session"""
        if session_id not in self.session_orders:
            return []
            
        # Get order IDs for this session (most recent first)
        order_ids = sorted(
            self.session_orders[session_id],
            key=lambda oid: self.orders[oid]['created_at'] if oid in self.orders else 0,
            reverse=True
        )
        
        # Get the orders (limited by max_count)
        recent_orders = []
        for order_id in order_ids[:max_count]:
            if order_id in self.orders:
                recent_orders.append(self.orders[order_id])
        
        return recent_orders
    
    def clear_session_orders(self, session_id: str):
        """Clear orders for a session"""
        if session_id not in self.session_orders:
            return
            
        # Get order IDs for this session
        order_ids = self.session_orders[session_id]
        
        # Remove the orders
        for order_id in order_ids:
            if order_id in self.orders:
                del self.orders[order_id]
        
        # Clear session orders
        del self.session_orders[session_id]
        logger.info(f"Cleared orders for session {session_id}")