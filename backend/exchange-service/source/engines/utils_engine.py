# source/engines/utils_engine.py
from typing import Dict, Any, Optional
from decimal import Decimal
import logging


class EngineUtils:
    """Utility functions shared across all engines."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def get_symbol_currency(self, symbol: str, user_context: Any) -> str:
        """Get symbol's currency from equity manager."""
        try:
            # Access app_state directly from user_context object
            app_state = user_context.app_state
            if hasattr(app_state, 'equity_manager') and app_state.equity_manager:
                if hasattr(app_state.equity_manager, '_symbol_state'):
                    symbol_state = app_state.equity_manager._symbol_state.get(symbol)
                    if symbol_state and hasattr(symbol_state, 'last_currency'):
                        return symbol_state.last_currency

            # If we can't find the currency, log error and default to USD
            self.logger.error(f"No currency found for symbol {symbol} in equity manager, defaulting to USD")
            return 'USD'

        except Exception as e:
            self.logger.error(f"Error getting currency for symbol {symbol}: {e}")
            return 'USD'

    def get_symbol_latest_price(self, symbol: str, user_context: Any) -> Optional[Decimal]:
        """Get latest price for a symbol from equity manager."""
        try:
            # Access app_state directly from user_context object
            app_state = user_context.app_state
            if hasattr(app_state, 'equity_manager') and app_state.equity_manager:
                price = app_state.equity_manager.get_last_price(symbol)
                if price is not None:
                    return price

            self.logger.warning(f"No price available for symbol {symbol}")
            return None

        except Exception as e:
            self.logger.error(f"Error getting latest price for {symbol}: {e}")
            return None

    def get_symbol_adv63(self, symbol: str, user_context: Any) -> Optional[Decimal]:
        """Get adv63 for a symbol from equity manager."""
        try:
            # Access app_state directly from user_context object
            app_state = user_context.app_state
            if hasattr(app_state, 'equity_manager') and app_state.equity_manager:
                adv63 = 1E9 # app_state.equity_manager.get_last_price(symbol)
                if adv63 is not None:
                    return adv63

            self.logger.warning(f"No adv63 available for symbol {symbol}")
            return None

        except Exception as e:
            self.logger.error(f"Error getting adv63 for {symbol}: {e}")
            return None

    def convert_to_base_currency(self, amount: Decimal, from_currency: str, base_currency: str,
                                 user_context: Any) -> Decimal:
        """Convert amount from one currency to base currency using FX manager."""
        if from_currency == base_currency:
            return amount

        try:
            # Access app_state directly from user_context object
            app_state = user_context.app_state
            if hasattr(app_state, 'fx_manager') and app_state.fx_manager:
                converted = app_state.fx_manager.convert(amount, from_currency, base_currency)
                if converted is not None:
                    return converted

            # If no FX conversion available, assume 1:1 rate with warning
            self.logger.warning(f"No FX rate available for {from_currency} to {base_currency}, using 1:1 rate")
            return amount

        except Exception as e:
            self.logger.error(f"Error converting {amount} from {from_currency} to {base_currency}: {e}")
            return amount

    def get_engine_info(self, engine_id: int, engine_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Get engine information and capabilities."""
        return {
            'engine_id': engine_id,
            'engine_name': engine_name,
            'config': config
        }