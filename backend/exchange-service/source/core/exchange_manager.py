# source/core/exchange_manager.py
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple

from source.models.enums import OrderSide
from source.core.market_data_manager import MarketDataClient
from source.core.order_manager import OrderManager
from source.db.database import DatabaseManager
from source.api.rest.health import HealthService

logger = logging.getLogger('exchange_manager')


class ExchangeManager:
    def __init__(self, user_id: str, desk_id: str, initial_cash: float = 100_000.0):
        self.user_id = user_id
        self.desk_id = desk_id
        self.initial_cash = initial_cash

        # Configuration
        self.default_symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN']

        # Core components
        self.market_data_client = MarketDataClient(self, self.default_symbols)
        self.order_manager = OrderManager(self)
        self.database_manager = DatabaseManager()

        # Market data storage
        self.current_market_data = {}  # symbol -> market data

        # Exchange state
        self.cash_balance = initial_cash
        self.positions: Dict[str, Dict] = {}
        self.orders: Dict[str, Dict] = {}

        # Add a queue for market data update notifications
        self.market_data_updates = asyncio.Queue()

        # Add health service for status tracking
        self.health_service = HealthService(self, http_port=50056)

    
    def get_health_service(self):
        """Get the health service instance"""
        return self.health_service

    async def initialize(self):
        """
        Initialize the exchange state with status reporting
        """
        try:
            logger.info("Initializing exchange components...")
            
            # Initialize database connection
            try:
                await self.database_manager.connect()
                connection_healthy = await self.database_manager.check_connection()
                if connection_healthy:
                    self.health_service.mark_service_ready('database', True)
                    logger.info("✓ Database connection established")
                else:
                    logger.warning("Database connection established but not responding to queries")
                    
            except Exception as e:
                logger.error(f"Failed to initialize database connection: {e}")
                raise

            # Load historical data
            historical_data = await self.database_manager.load_user_exchange_state(
                user_id=self.user_id,
                desk_id=self.desk_id
            )

            # Restore state if exists
            if historical_data:
                self.cash_balance = historical_data.get('cash_balance', self.initial_cash)
                self.positions = historical_data.get('positions', {})
                logger.info("✓ Historical state restored")

            # Initialize order manager
            await self.order_manager.initialize()
            if getattr(self.order_manager, 'connected', False):
                self.health_service.mark_service_ready('order_manager', True)
                logger.info("✓ Order manager connected")

            # Start the market data client
            await self.market_data_client.start()
            # Give it a moment to establish connection
            await asyncio.sleep(2)
            if getattr(self.market_data_client, 'running', False):
                self.health_service.mark_service_ready('market_data', True)
                logger.info("✓ Market data client started")

            logger.info(f"✓ Exchange initialized for User {self.user_id}")
            
        except Exception as e:
            logger.error(f"Exchange initialization failed: {e}")
            raise

    async def cleanup(self):
        """
        Perform cleanup operations
        - Save final state
        - Close database connections
        - Stop market data client
        """
        try:
            # Clean up order manager
            await self.order_manager.cleanup()

            # Stop the market data client
            await self.market_data_client.stop()

            # Close database connection
            await self.database_manager.close()

            logger.info(f"Exchange cleaned up for User {self.user_id}")
        except Exception as e:
            logger.error(f"Exchange cleanup failed: {e}")

    async def update_market_data(self, market_data_list):
        """
        Update market data with values from the market data service
        
        Args:
            market_data_list: List of market data updates
        """
        try:
            # Update the internal market data cache
            for market_data in market_data_list:
                symbol = market_data.get('symbol')
                if symbol:
                    self.current_market_data[symbol] = market_data

            # Notify listeners about the update
            await self.market_data_updates.put(True)
            logger.debug(f"Received market data for {len(market_data_list)} symbols")

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
        Now using stored market data from the market data service

        Returns:
        - Market data
        - Portfolio data
        - Order updates
        """
        symbols = symbols or self.default_symbols

        # Use the current market data
        market_data = []
        for symbol in symbols:
            if symbol in self.current_market_data:
                market_data.append(self.current_market_data[symbol])

        # If we don't have market data yet, return empty data
        if not market_data:
            logger.warning("No market data available yet")
            # Create minimal placeholder data
            market_data = [
                {'symbol': s, 'open': 0, 'high': 0, 'low': 0, 'close': 0, 'volume': 0, 'trade_count': 0, 'vwap': 0} for
                s in symbols]

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

    async def submit_order(
            self,
            symbol: str,
            side: str,
            quantity: float,
            order_type: str,
            price: Optional[float] = None,
            request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submit a trading order through the order manager"""
        try:
            # Convert string enums to proper enum types
            side_enum = OrderSide.BUY if side == "BUY" else OrderSide.SELL
            order_type_enum = OrderType.MARKET if order_type == "MARKET" else OrderType.LIMIT

            # Submit through order manager
            order = await self.order_manager.submit_order(
                symbol=symbol,
                side=side_enum,
                quantity=quantity,
                order_type=order_type_enum,
                price=price
            )

            if order.status == OrderStatus.REJECTED:
                return {
                    'success': False,
                    'error_message': order.error_message or 'Order rejected'
                }

            # Update our portfolio if the order was successful
            if order.status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
                self._update_portfolio_from_order(order)

            return {
                'success': True,
                'order_id': order.order_id
            }

        except Exception as e:
            logger.error(f"Order submission error: {e}")
            return {'success': False, 'error_message': str(e)}

    def _process_order(self, **kwargs):
        """Internal method to process order details"""
        # Implement order processing logic
        order_id = kwargs.get('order_id')
        symbol = kwargs.get('symbol')
        side = kwargs.get('side')
        quantity = kwargs.get('quantity')
        price = kwargs.get('price')

        # Store the order
        self.orders[order_id] = {
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'price': price,
            'status': 'FILLED',  # Simplified - assuming immediate fill
            'filled_quantity': quantity,
            'average_price': price
        }

        # Update positions and cash
        if side == OrderSide.BUY:
            # Deduct cash
            self.cash_balance -= quantity * price

            # Update position
            if symbol not in self.positions:
                self.positions[symbol] = {
                    'quantity': 0,
                    'average_cost': 0
                }

            position = self.positions[symbol]
            total_cost = position['average_cost'] * position['quantity']
            new_quantity = position['quantity'] + quantity
            new_total_cost = total_cost + (quantity * price)

            position['quantity'] = new_quantity
            position['average_cost'] = new_total_cost / new_quantity if new_quantity > 0 else 0

        elif side == OrderSide.SELL:
            # Add cash
            self.cash_balance += quantity * price

            # Update position
            if symbol in self.positions:
                position = self.positions[symbol]
                position['quantity'] -= quantity

                # Remove position if quantity is zero or negative
                if position['quantity'] <= 0:
                    del self.positions[symbol]

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an existing order through the order manager"""
        try:
            success = await self.order_manager.cancel_order(order_id)

            if success:
                return {'success': True}
            else:
                return {'success': False, 'error_message': 'Order cancellation failed'}

        except Exception as e:
            logger.error(f"Order cancellation error: {e}")
            return {'success': False, 'error_message': str(e)}

    def _update_portfolio_from_order(self, order):
        """Update portfolio based on order execution"""
        if order.side == OrderSide.BUY:
            # Deduct cash
            self.cash_balance -= order.filled_quantity * order.average_price

            # Update position
            if order.symbol not in self.positions:
                self.positions[order.symbol] = {
                    'quantity': 0,
                    'average_cost': 0
                }

            position = self.positions[order.symbol]
            total_cost = position['average_cost'] * position['quantity']
            new_quantity = position['quantity'] + order.filled_quantity
            new_total_cost = total_cost + (order.filled_quantity * order.average_price)

            position['quantity'] = new_quantity
            position['average_cost'] = new_total_cost / new_quantity if new_quantity > 0 else 0

        elif order.side == OrderSide.SELL:
            # Add cash
            self.cash_balance += order.filled_quantity * order.average_price

            # Update position
            if order.symbol in self.positions:
                position = self.positions[order.symbol]
                position['quantity'] -= order.filled_quantity

                # Remove position if quantity is zero or negative
                if position['quantity'] <= 0:
                    del self.positions[order.symbol]

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
            price = next((md['close'] for md in market_data if md['symbol'] == symbol), 0)
            return price

        # Use cached market data if available
        if symbol in self.current_market_data:
            return self.current_market_data[symbol].get('close', 0)

        return 0  # No price data available
