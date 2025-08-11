# source/conviction_engine/alpha_engines/target_weight/order_generator.py
from typing import Dict, List
import logging


class OrderGenerator:
    """Generates executable orders from portfolio changes"""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)

    def generate_orders(self,
                        target_portfolio: Dict[str, float],
                        current_portfolio: Dict[str, float],
                        urgency_map: Dict[str, str]) -> List[Dict]:
        """
        Generate orders from portfolio changes

        Returns:
            List of order dictionaries
        """

        orders = []
        all_symbols = set(list(target_portfolio.keys()) + list(current_portfolio.keys()))

        for symbol in all_symbols:
            target_weight = target_portfolio.get(symbol, 0.0)
            current_weight = current_portfolio.get(symbol, 0.0)

            delta_weight = target_weight - current_weight

            if self._is_meaningful_change(delta_weight):
                order = self._create_order(
                    symbol=symbol,
                    target_weight=target_weight,
                    current_weight=current_weight,
                    delta_weight=delta_weight,
                    urgency=urgency_map.get(symbol, "MEDIUM")
                )
                orders.append(order)

        return orders

    def _is_meaningful_change(self, delta_weight: float) -> bool:
        """Check if weight change is meaningful enough to trade"""

        min_trade_size_weight = (
                self.config.get('execution', {}).get('min_trade_size', 10000) /
                self.config.get('operational', {}).get('aum', 100000000)
        )

        return abs(delta_weight) > min_trade_size_weight

    def _create_order(self,
                      symbol: str,
                      target_weight: float,
                      current_weight: float,
                      delta_weight: float,
                      urgency: str) -> Dict:
        """Create individual order"""

        aum = float(self.config.get('operational', {}).get('aum', 100000000))

        # Calculate notional amounts
        target_notional = target_weight * aum
        current_notional = current_weight * aum
        delta_notional = delta_weight * aum

        # Get urgency parameters
        urgency_params = self._get_urgency_parameters(urgency)

        return {
            'symbol': symbol,
            'target_weight': target_weight,
            'current_weight': current_weight,
            'delta_weight': delta_weight,
            'target_notional': target_notional,
            'current_notional': current_notional,
            'delta_notional': delta_notional,
            'side': 'BUY' if delta_notional > 0 else 'SELL',
            'quantity': abs(delta_notional),
            'urgency': urgency,
            'participation_rate': urgency_params['participation_rate'],
            'max_duration_hours': urgency_params['max_duration_hours'],
            'order_type': self.config.get('execution', {}).get('order_type', 'VWAP_A_ALGO'),
            'priority': urgency_params['priority']
        }

    def _get_urgency_parameters(self, urgency: str) -> Dict:
        """Get execution parameters for urgency level"""

        default_params = {
            'HIGH': {'participation_rate': 0.30, 'max_duration_hours': 4, 'priority': 1},
            'MEDIUM': {'participation_rate': 0.15, 'max_duration_hours': 8, 'priority': 2},
            'LOW': {'participation_rate': 0.05, 'max_duration_hours': 24, 'priority': 3}
        }

        config_params = self.config.get('execution', {}).get('urgency_parameters', {})

        return config_params.get(urgency, default_params.get(urgency, default_params['MEDIUM']))