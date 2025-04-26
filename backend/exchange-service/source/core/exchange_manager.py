import logging
import uuid
from typing import Dict, List, Any, Optional, Tuple

from source.models.enums import OrderSide
from source.core.market_data_manager import MarketDataGenerator
from source.db.database import DatabaseManager

logger = logging.getLogger('exchange_manager')


class ExchangeManager:
    def __init__(self, user_id: str, desk_id: str, initial_cash: float = 100_000.0):
        self.user_id = user_id
        self.desk_id = desk_id
        self.initial_cash = initial_cash

        # Configuration
        self.default_symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN']

        # Core components
        self.market_data_generator = MarketDataGenerator(self.default_symbols)
        self.database_manager = DatabaseManager()

        # Exchange state
        self.cash_balance = initial_cash
        self.positions: Dict[str, Dict] = {}
        self.orders: Dict[str, Dict] = {}

    async def initialize(self):
        """
        Initialize the exchange state
        - Load historical positions
        - Restore previous state if applicable
        """
        try:
            try:
                # Attempt to connect to the database
                await self.database_manager.connect()

                # Verify connection
                connection_healthy = await self.database_manager.check_connection()
                if not connection_healthy:
                    logger.warning("Database connection established but not responding to queries")

            except Exception as e:
                logger.error(f"Failed to initialize database connection: {e}")
                # Decide how to handle: retry, exit, or continue with limited functionality
                raise

            # Load historical data for user
            historical_data = await self.database_manager.load_user_exchange_state(
                user_id=self.user_id,
                desk_id=self.desk_id
            )

            # Restore state if exists
            if historical_data:
                self.cash_balance = historical_data.get('cash_balance', self.initial_cash)
                self.positions = historical_data.get('positions', {})

            logger.info(f"Exchange initialized for User {self.user_id}")
        except Exception as e:
            logger.error(f"Exchange initialization failed: {e}")
            raise

    async def cleanup(self):
        """
        Perform cleanup operations
        - Save final state
        - Close database connections
        """
        try:
            # Close database connection
            await self.database_manager.close()

            logger.info(f"Exchange cleaned up for User {self.user_id}")
        except Exception as e:
            logger.error(f"Exchange cleanup failed: {e}")

    def update_market_data(self, market_data_list):
        """
        Update market data with values from the distributor
        
        Args:
            market_data_list: List of market data updates
        """
        try:
            # Update the market data in the market data generator
            for market_data in market_data_list:
                symbol = market_data.get('symbol')
                price = market_data.get('last_price')
                
                if symbol and price:
                    self.market_data_generator.prices[symbol] = price
            
            return True
        except Exception as e:
            logger.error(f"Failed to update market data: {e}")
            return False
        
    def generate_periodic_data(
            self,
            symbols: Optional[List[str]] = None
    ) -> Tuple[List[Dict], Dict, List[Dict]]:
        """
        Generate periodic market, portfolio, and order data

        Returns:
        - Market data
        - Portfolio data
        - Order updates
        """
        symbols = symbols or self.default_symbols

        # Generate market data
        market_data = self.market_data_generator.get_market_data(symbols)

        # Generate portfolio data
        portfolio_data = {
            'cash_balance': self.cash_balance,
            'total_value': self._calculate_total_portfolio_value(market_data),
            'positions': [
                {
                    'symbol': symbol,
                    'quantity': position['quantity'],
                    'average_cost': position['average_cost'],
                    'market_value': position['quantity'] * self._get_current_price(symbol, market_data)
                }
                for symbol, position in self.positions.items()
            ]
        }

        # Generate order updates
        order_updates = [
            {
                'order_id': order_id,
                'symbol': order['symbol'],
                'status': order['status'],
                'filled_quantity': order.get('filled_quantity', 0),
                'average_price': order.get('average_price', 0)
            }
            for order_id, order in self.orders.items()
        ]

        return market_data, portfolio_data, order_updates

    def submit_order(
            self,
            symbol: str,
            side: str,
            quantity: float,
            order_type: str,
            price: Optional[float] = None,
            request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submit a trading order"""
        try:
            # Validate order parameters
            if quantity <= 0:
                return {'success': False, 'error_message': 'Invalid quantity'}

            # Get current market price
            current_price = self._get_current_price(symbol)
            order_price = price or current_price

            # Order ID generation
            order_id = str(uuid.uuid4())

            # Buying power and position checks
            if side == OrderSide.BUY:
                total_cost = order_price * quantity
                if total_cost > self.cash_balance:
                    return {'success': False, 'error_message': 'Insufficient funds'}

            elif side == OrderSide.SELL:
                current_position = self.positions.get(symbol, {})
                if current_position.get('quantity', 0) < quantity:
                    return {'success': False, 'error_message': 'Insufficient position'}

            # Execute order logic
            self._process_order(
                order_id=order_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                price=order_price
            )

            return {
                'success': True,
                'order_id': order_id
            }

        except Exception as e:
            logger.error(f"Order submission error: {e}")
            return {'success': False, 'error_message': str(e)}

    def _process_order(self, **kwargs):
        """Internal method to process order details"""
        # Implement order processing logic
        pass

    def cancel_order(self, order_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Cancel an existing order"""
        try:
            if order_id not in self.orders:
                return {'success': False, 'error_message': 'Order not found'}

            # Mark order as cancelled
            self.orders[order_id]['status'] = 'CANCELLED'

            return {'success': True}

        except Exception as e:
            logger.error(f"Order cancellation error: {e}")
            return {'success': False, 'error_message': str(e)}

    def _calculate_total_portfolio_value(self, market_data: List[Dict]) -> float:
        """Calculate total portfolio value"""
        portfolio_value = self.cash_balance

        for symbol, position in self.positions.items():
            current_price = self._get_current_price(symbol, market_data)
            portfolio_value += position['quantity'] * current_price

        return portfolio_value

    def _get_current_price(
            self,
            symbol: str,
            market_data: Optional[List[Dict]] = None
    ) -> float:
        """Get current market price for a symbol"""
        if market_data:
            price = next((md['last_price'] for md in market_data if md['symbol'] == symbol), 0)
            return price

        return self.market_data_generator.get_current_price(symbol)
