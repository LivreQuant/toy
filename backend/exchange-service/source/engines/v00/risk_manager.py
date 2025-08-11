# source/conviction_engine/alpha_engines/target_weight/risk_manager.py
from typing import Dict, List, Tuple, Optional
import logging


class RiskManager:
    """Configuration-driven risk constraint manager"""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Extract risk configuration
        self.firm_risk_config = config.get('risk_manager', {}).get('firm_risk', {})
        self.sector_config = config.get('risk_manager', {}).get('sector_limits', {})
        self.concentration_config = config.get('risk_manager', {}).get('concentration_limits', {})
        self.factor_config = config.get('risk_manager', {}).get('factor_limits', {})
        self.risk_model_config = config.get('risk_manager', {}).get('risk_model', {})

    def apply_risk_constraints(self,
                               portfolio: Dict[str, float],
                               market_data: Optional[Dict] = None) -> Tuple[Dict[str, float], List[Dict]]:
        """Apply all enabled risk constraints"""

        constraint_log = []
        constrained_portfolio = portfolio.copy()

        # Apply firm position limits if enabled
        if self.firm_risk_config.get('enable_firm_limits', True):
            constrained_portfolio, pos_log = self._apply_position_limits(constrained_portfolio)
            constraint_log.extend(pos_log)

        # Apply sector limits if enabled and market data available
        if self.sector_config.get('enable', False) and market_data:
            constrained_portfolio, sector_log = self._apply_sector_limits(constrained_portfolio, market_data)
            constraint_log.extend(sector_log)

        # Apply concentration limits if enabled
        if self.concentration_config.get('enable', False) and market_data:
            constrained_portfolio, conc_log = self._apply_concentration_limits(constrained_portfolio, market_data)
            constraint_log.extend(conc_log)

        # Apply factor limits if enabled
        if self.factor_config.get('enable', False) and market_data:
            constrained_portfolio, factor_log = self._apply_factor_limits(constrained_portfolio, market_data)
            constraint_log.extend(factor_log)

        return constrained_portfolio, constraint_log

    def _apply_position_limits(self, portfolio: Dict[str, float]) -> Tuple[Dict[str, float], List[Dict]]:
        """Apply firm-wide position size limits from configuration"""

        constraint_log = []
        constrained_portfolio = portfolio.copy()

        firm_max = self.firm_risk_config.get('max_single_position', 0.05)

        for symbol, weight in portfolio.items():
            if abs(weight) > firm_max:
                old_weight = weight
                new_weight = firm_max if weight > 0 else -firm_max
                constrained_portfolio[symbol] = new_weight

                constraint_log.append({
                    'constraint': 'firm_position_limit',
                    'component': 'risk_manager',
                    'symbol': symbol,
                    'original_weight': old_weight,
                    'constrained_weight': new_weight,
                    'limit': firm_max,
                    'impact': abs(old_weight - new_weight)
                })

        return constrained_portfolio, constraint_log

    def _apply_sector_limits(self,
                             portfolio: Dict[str, float],
                             market_data: Dict) -> Tuple[Dict[str, float], List[Dict]]:
        """Apply sector exposure limits from configuration"""

        constraint_log = []

        # Get sector mappings from market data
        sector_map = {symbol: data.get('sector', 'Unknown')
                      for symbol, data in market_data.items()}

        # Calculate sector exposures
        sector_exposures = {}
        for symbol, weight in portfolio.items():
            sector = sector_map.get(symbol, 'Unknown')
            if sector not in sector_exposures:
                sector_exposures[sector] = 0.0
            sector_exposures[sector] += weight

        # Get sector limits from config (excluding 'enable' key)
        sector_limits = {k: v for k, v in self.sector_config.items() if k != 'enable'}
        constrained_portfolio = portfolio.copy()

        for sector, exposure in sector_exposures.items():
            limit = sector_limits.get(sector.lower(), float('inf'))

            if abs(exposure) > limit:
                # Scale down all positions in this sector proportionally
                sector_symbols = [s for s, data in market_data.items()
                                  if data.get('sector', '').lower() == sector.lower() and s in portfolio]

                if sector_symbols:
                    scale_factor = limit / abs(exposure)

                    for symbol in sector_symbols:
                        old_weight = constrained_portfolio[symbol]
                        new_weight = old_weight * scale_factor
                        constrained_portfolio[symbol] = new_weight

                        constraint_log.append({
                            'constraint': 'sector_limit',
                            'component': 'risk_manager',
                            'symbol': symbol,
                            'sector': sector,
                            'original_weight': old_weight,
                            'constrained_weight': new_weight,
                            'sector_limit': limit,
                            'scale_factor': scale_factor,
                            'impact': abs(old_weight - new_weight)
                        })

        return constrained_portfolio, constraint_log

    def _apply_concentration_limits(self,
                                    portfolio: Dict[str, float],
                                    market_data: Dict) -> Tuple[Dict[str, float], List[Dict]]:
        """Apply concentration limits from configuration"""

        constraint_log = []
        constrained_portfolio = portfolio.copy()

        # Apply issuer concentration limits
        max_issuer_exposure = self.concentration_config.get('max_single_issuer', 0.05)

        for symbol, weight in portfolio.items():
            if abs(weight) > max_issuer_exposure:
                old_weight = weight
                new_weight = max_issuer_exposure if weight > 0 else -max_issuer_exposure
                constrained_portfolio[symbol] = new_weight

                constraint_log.append({
                    'constraint': 'issuer_concentration_limit',
                    'component': 'risk_manager',
                    'symbol': symbol,
                    'original_weight': old_weight,
                    'constrained_weight': new_weight,
                    'limit': max_issuer_exposure,
                    'impact': abs(old_weight - new_weight)
                })

        # Apply country concentration limits
        max_country_exposure = self.concentration_config.get('max_single_country', 0.60)

        # Calculate country exposures
        country_exposures = {}
        for symbol, weight in constrained_portfolio.items():
            country = market_data.get(symbol, {}).get('country', 'Unknown')
            if country not in country_exposures:
                country_exposures[country] = 0.0
            country_exposures[country] += weight

        # Apply country limits
        for country, exposure in country_exposures.items():
            if abs(exposure) > max_country_exposure:
                # Scale down all positions in this country proportionally
                country_symbols = [s for s, data in market_data.items()
                                   if data.get('country') == country and s in constrained_portfolio]

                if country_symbols:
                    scale_factor = max_country_exposure / abs(exposure)

                    for symbol in country_symbols:
                        old_weight = constrained_portfolio[symbol]
                        new_weight = old_weight * scale_factor
                        constrained_portfolio[symbol] = new_weight

                        constraint_log.append({
                            'constraint': 'country_concentration_limit',
                            'component': 'risk_manager',
                            'symbol': symbol,
                            'country': country,
                            'original_weight': old_weight,
                            'constrained_weight': new_weight,
                            'country_limit': max_country_exposure,
                            'scale_factor': scale_factor,
                            'impact': abs(old_weight - new_weight)
                        })

        return constrained_portfolio, constraint_log

    def _apply_factor_limits(self,
                             portfolio: Dict[str, float],
                             market_data: Dict) -> Tuple[Dict[str, float], List[Dict]]:
        """Apply factor exposure limits from configuration"""

        constraint_log = []
        constrained_portfolio = portfolio.copy()

        # Get factor limits from config (excluding 'enable' key)
        factor_limits = {k.replace('max_', '').replace('_exposure', ''): v
                         for k, v in self.factor_config.items()
                         if k.startswith('max_') and k.endswith('_exposure')}

        # Calculate factor exposures
        for factor_name, limit in factor_limits.items():
            factor_exposure = 0.0

            for symbol, weight in constrained_portfolio.items():
                # Get factor loading from market data
                factor_loading = market_data.get(symbol, {}).get(factor_name, 0.0)
                factor_exposure += weight * factor_loading

            if abs(factor_exposure) > limit:
                # This is simplified - in practice would use optimization to reduce factor exposure
                # while minimizing portfolio changes
                scale_factor = limit / abs(factor_exposure)

                # Scale down positions with high factor loadings
                high_loading_symbols = [
                    symbol for symbol, weight in constrained_portfolio.items()
                    if abs(market_data.get(symbol, {}).get(factor_name, 0.0)) > 0.5 and
                       (weight * factor_exposure > 0)  # Same direction as total exposure
                ]

                for symbol in high_loading_symbols:
                    old_weight = constrained_portfolio[symbol]
                    new_weight = old_weight * scale_factor
                    constrained_portfolio[symbol] = new_weight

                    constraint_log.append({
                        'constraint': 'factor_exposure_limit',
                        'component': 'risk_manager',
                        'symbol': symbol,
                        'factor': factor_name,
                        'original_weight': old_weight,
                        'constrained_weight': new_weight,
                        'factor_limit': limit,
                        'scale_factor': scale_factor,
                        'impact': abs(old_weight - new_weight)
                    })

        return constrained_portfolio, constraint_log