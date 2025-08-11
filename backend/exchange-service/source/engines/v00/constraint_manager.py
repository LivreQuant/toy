# source/conviction_engine/alpha_engines/target_weight/constraint_manager.py
from typing import Dict, List, Tuple, Optional
import logging


class ConstraintManager:
    """Applies PM operational constraints"""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)

    def apply_operational_constraints(self,
                                      portfolio: Dict[str, float],
                                      market_data: Optional[Dict] = None) -> Tuple[Dict[str, float], List[Dict]]:
        """
        Apply PM operational constraints

        Returns:
            constrained_portfolio: Portfolio after operational constraints
            constraint_log: Log of applied constraints
        """

        constraint_log = []
        constrained_portfolio = portfolio.copy()

        # Apply PM position size limits
        constrained_portfolio, pos_log = self._apply_pm_position_limits(constrained_portfolio)
        constraint_log.extend(pos_log)

        # Apply liquidity constraints if enabled
        if (self.config.get('operational', {}).get('enable_liquidity_limits', False) and
                market_data):
            constrained_portfolio, liq_log = self._apply_liquidity_constraints(
                constrained_portfolio, market_data
            )
            constraint_log.extend(liq_log)

        return constrained_portfolio, constraint_log

    def _apply_pm_position_limits(self, portfolio: Dict[str, float]) -> Tuple[Dict[str, float], List[Dict]]:
        """Apply PM-level position size limits"""

        constraint_log = []
        constrained_portfolio = portfolio.copy()

        pm_max = self.config.get('operational', {}).get('max_position_size', 0.10)

        for symbol, weight in portfolio.items():
            if abs(weight) > pm_max:
                old_weight = weight
                new_weight = pm_max if weight > 0 else -pm_max
                constrained_portfolio[symbol] = new_weight

                constraint_log.append({
                    'constraint': 'pm_position_limit',
                    'component': 'constraint_manager',
                    'symbol': symbol,
                    'original_weight': old_weight,
                    'constrained_weight': new_weight,
                    'limit': pm_max,
                    'impact': abs(old_weight - new_weight)
                })

        return constrained_portfolio, constraint_log

    def _apply_liquidity_constraints(self,
                                     portfolio: Dict[str, float],
                                     market_data: Dict) -> Tuple[Dict[str, float], List[Dict]]:
        """Apply liquidity constraints"""

        constraint_log = []
        constrained_portfolio = portfolio.copy()

        aum = self.config.get('operational', {}).get('aum', 100000000)
        max_adv = self.config.get('firm_risk', {}).get('liquidity_constraints', {}).get('max_adv_participation', 0.05)

        for symbol, weight in portfolio.items():
            market_info = market_data.get(symbol, {})
            daily_volume = market_info.get('avg_daily_volume_usd', float('inf'))

            # Calculate maximum position based on ADV constraint
            max_position_usd = daily_volume * max_adv
            max_position_weight = max_position_usd / aum

            if abs(weight) > max_position_weight:
                old_weight = weight
                new_weight = max_position_weight if weight > 0 else -max_position_weight
                constrained_portfolio[symbol] = new_weight

                constraint_log.append({
                    'constraint': 'liquidity_limit',
                    'component': 'constraint_manager',
                    'symbol': symbol,
                    'original_weight': old_weight,
                    'constrained_weight': new_weight,
                    'daily_volume_usd': daily_volume,
                    'max_adv_participation': max_adv,
                    'impact': abs(old_weight - new_weight)
                })

        return constrained_portfolio, constraint_log