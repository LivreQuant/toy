import time
import uuid
import random
import logging
from typing import Dict, List, Any, Optional

from source.models.order import Order, OrderSide, OrderType, OrderStatus

logger = logging.getLogger(__name__)


class OrderManager:
    def __init__(self, portfolio_manager, market_data_generator):
        self.portfolio_manager = portfolio_manager
        self.market_data = market_data_generator
        self.orders = {}  # order_id -> Order
        self.session_orders = {}  # session_id -> list of order_ids
        self.request_ids = {}  # session_id:request_id -> order_id

    def create_random_order(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Create a random order for a session"""
        # Random chance of generating an order (10%)
        if random.random() > 0.1:
            return None

        # Get symbols
        symbols = self.market_data.symbols

        # Create random order
        symbol = random.choice(symbols)
        side = random.choice([OrderSide.BUY, OrderSide.SELL])
        quantity = random.randint(1, 10) * 10  # 10, 20, ..., 100
        price = self.market_data.get_price(symbol)
        order_type = OrderType.MARKET

        # Create and submit order
        order = Order(
            session_id=session_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price
        )

        # Process the order
        self._process_order(order)

        return order.to_dict()

    def submit_order(self, session_id: str, symbol: str, side: str,
                     quantity: float, price: Optional[float],
                     order_type: str, request_id: Optional[str] = None) -> Dict[str, Any]:
        """Submit a new order from external request"""
        # Check for duplicate request
        if request_id:
            request_key = f"{session_id}:{request_id}"
            if request_key in self.request_ids:
                existing_order_id = self.request_ids[request_key]
                existing_order = self.orders.get(existing_order_id)
                if existing_order:
                    logger.info(f"Found duplicate request {request_id}, returning existing order {existing_order_id}")
                    return {
                        'success': True,
                        'order_id': existing_order_id,
                        'duplicate': True
                    }

        # Validate basic parameters
        if not symbol or quantity <= 0:
            return {
                'success': False,
                'error_message': "Invalid order parameters"
            }

        # Map side and type to enum values
        try:
            order_side = OrderSide(side.upper())
        except ValueError:
            return {
                'success': False,
                'error_message': f"Invalid order side: {side}"
            }

        try:
            order_order_type = OrderType(order_type.upper())
        except ValueError:
            return {
                'success': False,
                'error_message': f"Invalid order type: {order_type}"
            }

        # Create order object
        order = Order(
            session_id=session_id,
            symbol=symbol,
            side=order_side,
            quantity=quantity,
            price=price,
            order_type=order_order_type,
            request_id=request_id
        )

        # Store request ID mapping if provided
        if request_id:
            request_key = f"{session_id}:{request_id}"
            self.request_ids[request_key] = order.order_id

        # Process the order
        result = self._process_order(order)

        if result:
            return {
                'success': True,
                'order_id': order.order_id
            }
        else:
            return {
                'success': False,
                'error_message': order.error_message or "Order processing failed"
            }

    def cancel_order(self, session_id: str, order_id: str) -> Dict[str, Any]:
        """Cancel an existing order"""
        # Check if order exists
        if order_id not in self.orders:
            return {
                'success': False,
                'error_message': "Order not found"
            }

        order = self.orders[order_id]

        # Check if order belongs to session
        if order.session_id != session_id:
            return {
                'success': False,
                'error_message': "Order does not belong to this session"
            }

        # Check if order can be canceled
        if order.status not in [OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED]:
            return {
                'success': False,
                'error_message': f"Cannot cancel order in state {order.status}"
            }

        # Cancel the order
        order.status = OrderStatus.CANCELED
        order.updated_at = time.time()
        order.error_message = "Canceled by user"

        logger.info(f"Order {order_id} canceled")
        return {
            'success': True
        }

    def get_order_status(self, session_id: str, order_id: str) -> Dict[str, Any]:
        """Get status of an existing order"""
        # Check if order exists
        if order_id not in self.orders:
            return {
                'success': False,
                'error_message': "Order not found"
            }

        order = self.orders[order_id]

        # Check if order belongs to session
        if order.session_id != session_id:
            return {
                'success': False,
                'error_message': "Order does not belong to this session"
            }

        # Map status to proto enum
        status_map = {
            OrderStatus.NEW: 1,
            OrderStatus.PARTIALLY_FILLED: 2,
            OrderStatus.FILLED: 3,
            OrderStatus.CANCELED: 4,
            OrderStatus.REJECTED: 5
        }

        status = status_map.get(order.status, 0)

        return {
            'success': True,
            'status': status,
            'filled_quantity': order.filled_quantity,
            'avg_price': order.average_price,
            'error_message': order.error_message
        }

    def _process_order(self, order: Order) -> bool:
        """Process an order and store it"""
        # Add to orders dict
        self.orders[order.order_id] = order

        # Add to session orders
        if order.session_id not in self.session_orders:
            self.session_orders[order.session_id] = []
        self.session_orders[order.session_id].append(order.order_id)

        # For simplicity in the simulator, we'll fill all market orders immediately
        if order.order_type == OrderType.MARKET:
            return self._execute_market_order(order)
        elif order.order_type == OrderType.LIMIT:
            # In a real exchange, limit orders would be added to an order book
            # For this simulator, we'll check if price is favorable and execute immediately if so
            return self._process_limit_order(order)

        return False

    def _execute_market_order(self, order: Order) -> bool:
        """Execute a market order"""
        # Get current price
        price = self.market_data.get_price(order.symbol)

        if price <= 0:
            order.status = OrderStatus.REJECTED
            order.error_message = "Invalid price"
            order.updated_at = time.time()
            return False

        # Execute in portfolio
        success = self.portfolio_manager.execute_trade(
            order.session_id,
            order.symbol,
            order.side.value,
            order.quantity,
            price
        )

        if success:
            # Update order status
            order.status = OrderStatus.FILLED
            order.filled_quantity = order.quantity
            order.average_price = price
            order.updated_at = time.time()
            logger.info(f"Market order {order.order_id} filled: {order.quantity} {order.symbol} @ {price}")
        else:
            # Mark as rejected
            order.status = OrderStatus.REJECTED
            order.error_message = "Insufficient funds or shares"
            order.updated_at = time.time()
            logger.warning(f"Market order {order.order_id} rejected")

        return success

    def _process_limit_order(self, order: Order) -> bool:
        """Process a limit order"""
        # Get current price
        price = self.market_data.get_price(order.symbol)

        if price <= 0:
            order.status = OrderStatus.REJECTED
            order.error_message = "Invalid price"
            order.updated_at = time.time()
            return False

        # Check if order can be executed based on price
        can_execute = False

        if order.side == OrderSide.BUY and price <= order.price:
            # For buy limit, execute if market price <= limit price
            can_execute = True
        elif order.side == OrderSide.SELL and price >= order.price:
            # For sell limit, execute if market price >= limit price
            can_execute = True

        if can_execute:
            # Execute at limit price (not market price)
            execution_price = order.price

            success = self.portfolio_manager.execute_trade(
                order.session_id,
                order.symbol,
                order.side.value,
                order.quantity,
                execution_price
            )

            if success:
                # Update order status
                order.status = OrderStatus.FILLED
                order.filled_quantity = order.quantity
                order.average_price = execution_price
                order.updated_at = time.time()
                logger.info(f"Limit order {order.order_id} filled: {order.quantity} {order.symbol} @ {execution_price}")
            else:
                # Mark as rejected
                order.status = OrderStatus.REJECTED
                order.error_message = "Insufficient funds or shares"
                order.updated_at = time.time()
                logger.warning(f"Limit order {order.order_id} rejected")

            return success
        else:
            # Order stays in NEW status
            logger.info(f"Limit order {order.order_id} added to book")
            return True

    def get_recent_orders(self, session_id: str, max_count: int = 10) -> List[Dict[str, Any]]:
        """Get recent orders for a session"""
        if session_id not in self.session_orders:
            return []

        # Get order IDs for this session (most recent first)
        order_ids = sorted(
            self.session_orders[session_id],
            key=lambda oid: self.orders[oid].created_at if oid in self.orders else 0,
            reverse=True
        )

        # Get the orders (limited by max_count)
        recent_orders = []
        for order_id in order_ids[:max_count]:
            if order_id in self.orders:
                recent_orders.append(self.orders[order_id].to_dict())

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
                # Get the order to check for request ID
                order = self.orders[order_id]
                if order.request_id:
                    request_key = f"{session_id}:{order.request_id}"
                    if request_key in self.request_ids:
                        del self.request_ids[request_key]

                # Remove the order
                del self.orders[order_id]

        # Clear session orders
        del self.session_orders[session_id]
        logger.info(f"Cleared orders for session {session_id}")
