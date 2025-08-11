# source/engines/base_engine.py
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from decimal import Decimal
import logging
import uuid
from datetime import datetime
from .utils_engine import EngineUtils


class BaseEngine(ABC):
    """Base class for all conviction-to-order conversion engines."""

    def __init__(self, engine_id: int, config: Dict[str, Any] = None):
        self.engine_id = engine_id
        self.config = config or {}
        self.logger = logging.getLogger(f"{self.__class__.__name__}_{engine_id}")

        # Initialize utils with logger
        self.utils = EngineUtils(self.logger)

    @abstractmethod
    def convert_convictions_to_orders(self,
                                      user_id: str,
                                      convictions: List[Dict[str, Any]],
                                      user_context: Any) -> List[Dict[str, Any]]:
        """Convert convictions to executable orders."""
        pass

    @abstractmethod
    def validate_conviction(self, conviction: Dict[str, Any]) -> str:
        """Validate a conviction for this engine."""
        pass

    def get_engine_info(self) -> Dict[str, Any]:
        """Get engine information and capabilities."""
        return self.utils.get_engine_info(self.engine_id, self.__class__.__name__, self.config)

    ############################
    # NOTIONAL BASED FUNCTIONS #
    ############################

    def get_current_notional_portfolio_from_manager(self, user_context: Any) -> Dict[str, float]:
        """
        SHARED METHOD: Get current portfolio notionals from portfolio manager in user_context.
        All notionals will be converted to user's base currency.
        """
        try:
            # Get portfolio manager from user_context
            app_state = user_context.app_state
            portfolio_manager = app_state.portfolio_manager

            base_currency = user_context.base_currency

            if not portfolio_manager:
                self.logger.warning("No portfolio manager in user_context")
                return {}

            # Get current positions
            if hasattr(portfolio_manager, 'get_all_positions'):
                positions = portfolio_manager.get_all_positions()
                return self._convert_positions_to_notional(positions, base_currency, user_context)
            else:
                self.logger.warning(f"Portfolio manager has no get_all_positions method: {type(portfolio_manager)}")
                return {}

        except Exception as e:
            self.logger.error(f"Error getting current portfolio from manager: {e}")
            return {}

    def _convert_positions_to_notional(self, positions: Dict, base_currency: str, user_context: Any) -> Dict[
        str, float]:
        """Convert position objects to portfolio notionals in base currency."""
        try:
            notionals = {}

            for symbol, position in positions.items():
                try:
                    if hasattr(position, 'quantity') and hasattr(position, 'mtm_value'):
                        # Use mark-to-market value for notional calculation
                        position_value = Decimal(str(position.mtm_value))
                        position_currency = getattr(position, 'currency', None)

                        # If position doesn't have currency, get it from symbol
                        if position_currency is None:
                            position_currency = self.utils.get_symbol_currency(symbol, user_context)

                        # Convert to base currency
                        notional_value = self.utils.convert_to_base_currency(
                            position_value, position_currency, base_currency, user_context
                        )

                        notionals[symbol] = float(notional_value)
                    else:
                        self.logger.warning(f"Position {symbol} missing mtm_value or quantity")

                except Exception as e:
                    self.logger.error(f"Error converting position {symbol}: {e}")
                    continue

            return notionals

        except Exception as e:
            self.logger.error(f"Error converting positions to notionals: {e}")
            return {}

    def _generate_orders_from_notional_solution(self,
                                                current_portfolio: Dict[str, float],
                                                optimal_portfolio: Dict[str, float],
                                                user_context: Any,
                                                convictions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate orders from optimization solution."""
        orders = []

        # Create conviction lookup for metadata
        conviction_map = {conv['instrument_id']: conv for conv in convictions}

        # Find all symbols that need trading
        all_symbols = set(list(current_portfolio.keys()) + list(optimal_portfolio.keys()))

        for symbol in all_symbols:
            current_notional = current_portfolio.get(symbol, 0.0)
            optimal_notional = optimal_portfolio.get(symbol, 0.0)

            # Calculate required change in base currency
            notional_delta = optimal_notional - current_notional

            print(f"A: {current_notional} - {optimal_notional} - {notional_delta}")

            # Skip if no change needed
            if abs(notional_delta) < 0.01:  # Minimum trade threshold
                continue

            # Get original conviction for metadata
            conviction = conviction_map.get(symbol, {})

            # Create order
            order = self._create_order_from_notional_change(
                symbol=symbol,
                notional_delta=notional_delta,
                conviction=conviction,
                user_context=user_context
            )

            if order:
                orders.append(order)

        return orders

    def _create_order_from_notional_change(self,
                                           symbol: str,
                                           notional_delta: float,
                                           conviction: Dict[str, Any],
                                           user_context: Any) -> Optional[Dict[str, Any]]:
        """Create order from notional change, converting to symbol quantity."""
        try:
            base_currency = user_context.base_currency

            # Get latest price for the symbol
            latest_price = self.utils.get_symbol_latest_price(symbol, user_context)
            if latest_price is None:
                self.logger.error(f"No price available for {symbol}, cannot create order")
                return None

            print(f"B: LATEST PRICE: {latest_price}")

            # Get symbol's native currency
            symbol_currency = self.utils.get_symbol_currency(symbol, user_context)

            # Convert notional delta from base currency to symbol currency
            notional_in_symbol_currency = self.utils.convert_to_base_currency(
                Decimal(str(abs(notional_delta))), base_currency, symbol_currency, user_context
            )

            # Convert to symbol quantity
            quantity = float(notional_in_symbol_currency) / float(latest_price)

            # Round to appropriate precision (typically 2 decimal places for shares)
            quantity = round(quantity)

            print(f"C: QUANTITY: {quantity}")

            if quantity <= 0:
                self.logger.warning(f"Calculated quantity <= 0 for {symbol}: {quantity}")
                return None

            # Determine order direction
            side = 'BUY' if notional_delta > 0 else 'SELL'

            # Map participation rate
            participation_rate_map = {
                'LOW': 0.01,
                'MEDIUM': 0.03,
                'HIGH': 0.05
            }

            participation_rate = participation_rate_map.get(
                conviction.get('participation_rate', 'MEDIUM'), 0.03
            )

            # Generate IDs
            conviction_id = conviction.get('conviction_id', f'OPT_{symbol}_{uuid.uuid4().hex[:8]}')
            order_id = f"ORD_{conviction_id}_{uuid.uuid4().hex[:8]}"

            # ✅ Use the submit timestamp from the conviction if available
            submit_timestamp = conviction.get('submit_timestamp')
            if submit_timestamp:
                if isinstance(submit_timestamp, str):
                    submit_timestamp = datetime.fromisoformat(submit_timestamp.replace('Z', '+00:00'))
            else:
                # Fallback to market time
                from source.orchestration.app_state.state_manager import app_state
                submit_timestamp = app_state.get_current_timestamp()

            return {
                'user_id': user_context.user_id,

                # Order identification
                'order_id': order_id,
                'cl_order_id': conviction_id,

                # Trading details
                'symbol': symbol,
                'side': side,

                'original_qty': quantity,
                'remaining_qty': quantity,
                'completed_qty': 0,

                'currency': symbol_currency,  # Use symbol's native currency
                'price': 0.0,
                'order_type': 'MARKET',

                'participation_rate': participation_rate,

                'submit_timestamp': submit_timestamp,

                #start_timestamp: datetime
                #cancelled: bool = False
                #cancel_timestamp: Optional[datetime] = None

                # Metadata
                'tag': conviction.get('tag', 'optimization'),
                'engine_id': f'ENGINE_{self.engine_id}',
            }

        except Exception as e:
            self.logger.error(f"Error creating order for {symbol}: {e}")
            return None

    ##########################
    # WEIGHT BASED FUNCTIONS #
    ##########################

    def get_current_weight_portfolio_from_manager(self, user_context: Any) -> Dict[str, float]:
        """
        SHARED METHOD: Get current portfolio weights from portfolio manager in user_context.
        This is the same across all engines.
        """
        try:
            # Get portfolio manager from user_context
            app_state = user_context.app_state
            portfolio_manager = app_state.portfolio_manager

            if not portfolio_manager:
                self.logger.warning("No portfolio manager in user_context")
                return {}

            # Get current positions
            if hasattr(portfolio_manager, 'get_all_positions'):
                positions = portfolio_manager.get_all_positions()
                return self._convert_positions_to_weights(positions, user_context)
            else:
                self.logger.warning(f"Portfolio manager has no get_all_positions method: {type(portfolio_manager)}")
                return {}

        except Exception as e:
            self.logger.error(f"Error getting current portfolio from manager: {e}")
            return {}

    def _convert_positions_to_weights(self, positions: Dict, user_context: Any) -> Dict[str, float]:
        """Convert position objects to portfolio weights in base currency."""
        try:
            weights = {}
            base_currency = user_context.base_currency

            # Get AUM from account for weight calculation (if available)
            account_manager = user_context.app_state.account_manager

            if hasattr(account_manager, 'get_total_value'):
                total_value = float(account_manager.get_total_value())
            else:
                self.logger.error(f"Error getting total_value")
                total_value = 100000000.0  # Default AUM fallback

            for symbol, position in positions.items():
                try:
                    if hasattr(position, 'mtm_value') and hasattr(position, 'quantity'):
                        # Get position value and currency
                        position_value = Decimal(str(position.mtm_value))
                        position_currency = getattr(position, 'currency', None)

                        # If position doesn't have currency, get it from symbol
                        if position_currency is None:
                            position_currency = self.utils.get_symbol_currency(symbol, user_context)

                        # Convert to base currency
                        position_value_base = self.utils.convert_to_base_currency(
                            position_value, position_currency, base_currency, user_context
                        )

                        weight = float(position_value_base) / total_value
                        weights[symbol] = weight
                    else:
                        self.logger.warning(f"Position {symbol} missing mtm_value or quantity")
                except Exception as e:
                    self.logger.error(f"Error converting position {symbol}: {e}")
                    continue

            return weights

        except Exception as e:
            self.logger.error(f"Error converting positions to weights: {e}")
            return {}

    def _create_order_from_weight_change(self,
                                         symbol: str,
                                         weight_delta: float,
                                         conviction: Dict[str, Any],
                                         user_context: Any) -> Optional[Dict[str, Any]]:
        """Create order from weight change."""
        try:
            # Get AUM to convert weight to notional
            account_manager = user_context.app_state.account_manager
            total_value = 100000000.0  # Default AUM fallback

            if hasattr(account_manager, 'get_total_value'):
                total_value = float(account_manager.get_total_value())

            # Convert weight delta to notional delta
            notional_delta = weight_delta * total_value

            # Use the notional order creation method
            return self._create_order_from_notional_change(
                symbol=symbol,
                notional_delta=notional_delta,
                conviction=conviction,
                user_context=user_context
            )

        except Exception as e:
            self.logger.error(f"Error creating order from weight change for {symbol}: {e}")
            return None

    def _generate_orders_from_weight_solution(self,
                                              current_portfolio: Dict[str, float],
                                              optimal_portfolio: Dict[str, float],
                                              user_context: Any,
                                              convictions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate orders from weight-based optimization solution."""
        orders = []

        # Create conviction lookup for metadata
        conviction_map = {conv['instrument_id']: conv for conv in convictions}

        # Find all symbols that need trading
        all_symbols = set(list(current_portfolio.keys()) + list(optimal_portfolio.keys()))

        for symbol in all_symbols:
            current_weight = current_portfolio.get(symbol, 0.0)
            optimal_weight = optimal_portfolio.get(symbol, 0.0)

            # Calculate required change
            weight_delta = optimal_weight - current_weight

            # Skip if no change needed
            if abs(weight_delta) < 0.0001:  # Minimum weight threshold
                continue

            # Get original conviction for metadata
            conviction = conviction_map.get(symbol, {})

            # Create order
            order = self._create_order_from_weight_change(
                symbol=symbol,
                weight_delta=weight_delta,
                conviction=conviction,
                user_context=user_context
            )

            if order:
                orders.append(order)

        return orders