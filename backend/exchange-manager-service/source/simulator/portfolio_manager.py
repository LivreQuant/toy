from typing import Dict, Any, List, Optional
import time
import logging

logger = logging.getLogger(__name__)

class PortfolioManager:
    def __init__(self):
        self.portfolios = {}  # session_id -> portfolio data
    
    def create_portfolio(self, session_id: str, initial_cash: float = 100000.0):
        """Create a new portfolio for session"""
        self.portfolios[session_id] = {
            'cash_balance': initial_cash,
            'positions': {},
            'created_at': time.time()
        }
        logger.info(f"Created portfolio for session {session_id} with {initial_cash} cash")
    
    def remove_portfolio(self, session_id: str):
        """Remove a portfolio"""
        if session_id in self.portfolios:
            del self.portfolios[session_id]
            logger.info(f"Removed portfolio for session {session_id}")
    
    def get_portfolio(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get portfolio data for a session"""
        return self.portfolios.get(session_id)
    
    def update_position_market_value(self, session_id: str, symbol: str, price: float):
        """Update the market value of a position based on current price"""
        if session_id not in self.portfolios:
            return
            
        portfolio = self.portfolios[session_id]
        if symbol in portfolio['positions']:
            position = portfolio['positions'][symbol]
            position['market_value'] = position['quantity'] * price
    
    def execute_trade(self, session_id: str, symbol: str, side: str, quantity: int, price: float):
        """Execute a trade in the portfolio"""
        if session_id not in self.portfolios:
            logger.warning(f"Trade failed: Portfolio not found for session {session_id}")
            return False
            
        portfolio = self.portfolios[session_id]
        
        # Calculate trade value
        trade_value = quantity * price
        
        # Process buy order
        if side.upper() == "BUY":
            # Check if enough cash
            if portfolio['cash_balance'] < trade_value:
                logger.warning(f"Buy order failed: Insufficient funds")
                return False
                
            # Deduct cash
            portfolio['cash_balance'] -= trade_value
            
            # Update position
            if symbol not in portfolio['positions']:
                portfolio['positions'][symbol] = {
                    'quantity': 0,
                    'average_cost': 0,
                    'market_value': 0
                }
                
            position = portfolio['positions'][symbol]
            
            # Calculate new position
            total_quantity = position['quantity'] + quantity
            total_cost = (position['quantity'] * position['average_cost']) + trade_value
            
            position['quantity'] = total_quantity
            position['average_cost'] = total_cost / total_quantity if total_quantity > 0 else 0
            position['market_value'] = total_quantity * price
            
        # Process sell order
        elif side.upper() == "SELL":
            # Check if enough shares
            if symbol not in portfolio['positions'] or portfolio['positions'][symbol]['quantity'] < quantity:
                logger.warning(f"Sell order failed: Insufficient shares")
                return False
                
            # Add cash
            portfolio['cash_balance'] += trade_value
            
            # Update position
            position = portfolio['positions'][symbol]
            position['quantity'] -= quantity
            position['market_value'] = position['quantity'] * price
            
            # Remove position if zero
            if position['quantity'] <= 0:
                del portfolio['positions'][symbol]
        
        return True