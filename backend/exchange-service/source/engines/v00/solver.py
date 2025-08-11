# source/conviction_engine/alpha_engines/target_weight/solver.py
from typing import Dict, List, Tuple
import logging


class TargetWeightSolver:
    """Solves target weight optimization (minimal for this engine)"""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)

    def solve(self,
              constrained_portfolio: Dict[str, float]) -> Tuple[Dict[str, float], List[Dict]]:
        """
        Solve for final portfolio weights

        For target weight engine, this is mainly leverage normalization

        Returns:
            final_portfolio: Final portfolio weights
            solver_log: Log of solver actions
        """

        solver_log = []

        # Normalize to target leverage
        final_portfolio, norm_log = self._normalize_leverage(constrained_portfolio)
        solver_log.extend(norm_log)

        # Remove tiny positions
        final_portfolio, cleanup_log = self._cleanup_positions(final_portfolio)
        solver_log.extend(cleanup_log)

        return final_portfolio, solver_log

    def _normalize_leverage(self, portfolio: Dict[str, float]) -> Tuple[Dict[str, float], List[Dict]]:
        """Normalize portfolio to target leverage"""

        solver_log = []
        target_leverage = self.config.get('operational', {}).get('target_leverage', 1.0)
        current_leverage = sum(portfolio.values())

        if abs(current_leverage) < 1e-6:
            return portfolio, solver_log

        if abs(current_leverage - target_leverage) > 1e-6:
            scale_factor = target_leverage / current_leverage

            normalized_portfolio = {
                symbol: weight * scale_factor
                for symbol, weight in portfolio.items()
            }

            solver_log.append({
                'action': 'leverage_normalization',
                'component': 'solver',
                'original_leverage': current_leverage,
                'target_leverage': target_leverage,
                'scale_factor': scale_factor,
                'impact': abs(current_leverage - target_leverage)
            })

            return normalized_portfolio, solver_log

        return portfolio, solver_log

    def _cleanup_positions(self, portfolio: Dict[str, float]) -> Tuple[Dict[str, float], List[Dict]]:
        """Remove positions below minimum size"""

        solver_log = []
        min_position = self.config.get('validation', {}).get('min_position_size', 0.001)

        cleaned_portfolio = {}

        for symbol, weight in portfolio.items():
            if abs(weight) >= min_position:
                cleaned_portfolio[symbol] = weight
            else:
                solver_log.append({
                    'action': 'position_cleanup',
                    'component': 'solver',
                    'symbol': symbol,
                    'removed_weight': weight,
                    'reason': 'below_minimum_size',
                    'min_size': min_position
                })

        return cleaned_portfolio, solver_log