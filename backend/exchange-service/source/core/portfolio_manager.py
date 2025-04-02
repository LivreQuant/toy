import time
from typing import Dict, List
from source.models.order import Order
from source.models.enums import OrderSide

class Portfolio:
    def __init__(self, user_id: str, initial_cash: float = 100000.0):
        self.user_id = user_id
        self.cash_balance = initial_cash
        self.positions: Dict[str, Dict] = {}

    def update_position(self, order: Order):
        """Update portfolio based on order execution"""
        symbol = order.symbol
        
        if symbol not in self.positions:
            self.positions[symbol] = {
                'quantity': 0,
                'avg_cost': 0.0,
                'market_value': 0.0
            }

        position = self.positions[symbol]
        total_cost = position['quantity'] * position['avg_cost']

        if order.side == OrderSide.BUY:
            # Adjust cash
            self.cash_balance -= order.filled_quantity * order.average_price
            
            # Update position
            new_total_quantity = position['quantity'] + order.filled_quantity
            new_total_cost = total_cost + (order.filled_quantity * order.average_price)
            
            position['quantity'] = new_total_quantity
            position['avg_cost'] = new_total_cost / new_total_quantity if new_total_quantity > 0 else 0
        
        elif order.side == OrderSide.SELL:
            # Adjust cash
            self.cash_balance += order.filled_quantity * order.average_price
            
            # Update position
            position['quantity'] -= order.filled_quantity
            
            # Remove position if quantity is zero
            if position['quantity'] <= 0:
                del self.positions[symbol]

    def get_total_value(self, market_prices: Dict[str, float]) -> float:
        """Calculate total portfolio value"""
        portfolio_value = self.cash_balance
        
        for symbol, position in self.positions.items():
            current_price = market_prices.get(symbol, 0)
            portfolio_value += position['quantity'] * current_price
        
        return portfolio_value

class PortfolioManager:
    def __init__(self):
        self.portfolios: Dict[str, Portfolio] = {}

    def create_portfolio(self, session_id: str, user_id: str, initial_cash: float = 100000.0):
        """Create a new portfolio for a session"""
        self.portfolios[session_id] = Portfolio(user_id, initial_cash)

    def get_portfolio(self, session_id: str) -> Portfolio:
        """Retrieve a portfolio"""
        return self.portfolios.get(session_id)

    def update_portfolio(self, session_id: str, order: Order):
        """Update portfolio for a specific session"""
        portfolio = self.portfolios.get(session_id)
        if portfolio:
            portfolio.update_position(order)