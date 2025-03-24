from typing import Dict, Any, List, Optional
import time
import logging

from source.models.portfolio import Portfolio, Position
from source.utils.metrics import Metrics, timed

logger = logging.getLogger(__name__)
metrics = Metrics()

class PortfolioManager:
    """Manages user portfolios"""
    
    def __init__(self):
        """Initialize portfolio manager"""
        self.portfolios = {}  # session_id -> portfolio

    def create_portfolio(self, session_id: str, user_id: str, initial_cash: float = 100000.0):
        """Create a new portfolio for session"""
        self.portfolios[session_id] = Portfolio(
            user_id=user_id,
            session_id=session_id,
            cash_balance=initial_cash
        )
        logger.info(f"Created portfolio for session {session_id} with {initial_cash} cash")
        metrics.increment_counter("portfolio_created")

    def remove_portfolio(self, session_id: str):
        """Remove a portfolio"""
        if session_id in self.portfolios:
            del self.portfolios[session_id]
            logger.info(f"Removed portfolio for session {session_id}")
            metrics.increment_counter("portfolio_removed")

    def get_portfolio(self, session_id: str) -> Optional[Portfolio]:
        """Get portfolio data for a session"""
        return self.portfolios.get(session_id)

    def update_position_market_value(self, session_id: str, symbol: str, price: float):
        """Update the market value of a position based on current price"""
        portfolio = self.get_portfolio(session_id)
        if not portfolio:
            return
            
        portfolio.update_position_market_value(symbol, price)

    @timed("execute_trade")
    def execute_trade(self, session_id: str, symbol: str, side: str, quantity: float, price: float) -> bool:
        """Execute a trade in the portfolio"""
        portfolio = self.get_portfolio(session_id)
        if not portfolio:
            logger.warning(f"Trade failed: Portfolio not found for session {session_id}")
            return False

        # Calculate trade value
        trade_value = quantity * price

        # Process buy order
        if side.upper() == "BUY":
            # Check if enough cash
            if portfolio.cash_balance < trade_value:
                logger.warning(f"Buy order failed: Insufficient funds")
                metrics.increment_counter("trade_failed", tags={"reason": "insufficient_funds"})
                return False

            # Deduct cash
            portfolio.cash_balance -= trade_value

            # Update position
            if symbol not in portfolio.positions:
                portfolio.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=0,
                    average_cost=0
                )

            position = portfolio.positions[symbol]

            # Calculate new position
            total_quantity = position.quantity + quantity
            total_cost = (position.quantity * position.average_cost) + trade_value

            position.quantity = total_quantity
            position.average_cost = total_cost / total_quantity if total_quantity > 0 else 0
            position.market_value = total_quantity * price
            
            metrics.increment_counter("trade_executed", tags={"side": "buy", "symbol": symbol})

        # Process sell order
        elif side.upper() == "SELL":
            # Check if enough shares
            if symbol not in portfolio.positions or portfolio.positions[symbol].quantity < quantity:
                logger.warning(f"Sell order failed: Insufficient shares")
                metrics.increment_counter("trade_failed", tags={"reason": "insufficient_shares"})
                return False

            # Add cash
            portfolio.cash_balance += trade_value

            # Update position
            position = portfolio.positions[symbol]
            position.quantity -= quantity
            position.market_value = position.quantity * price

            # Remove position if zero
            if position.quantity <= 0:
                del portfolio.positions[symbol]
                
            metrics.increment_counter("trade_executed", tags={"side": "sell", "symbol": symbol})

        # Update portfolio timestamp
        portfolio.updated_at = time.time()
        
        # Update portfolio metrics
        metrics.set_gauge(
            "portfolio_value", 
            portfolio.get_total_value(), 
            tags={"session_id": session_id}
        )
        metrics.set_gauge(
            "portfolio_cash", 
            portfolio.cash_balance, 
            tags={"session_id": session_id}
        )
        
        return True