# source/simulation/managers/risk.py
from threading import RLock
from typing import Dict, Optional, List, Callable, Tuple, TYPE_CHECKING
from datetime import datetime
from dataclasses import dataclass, field
import logging
from source.simulation.managers.utils import TrackingManager, CallbackManager

if TYPE_CHECKING:
    from typing import Tuple


@dataclass
class RiskSnapshot:
    """Represents a risk state snapshot"""
    timestamp: str
    symbol: str
    sector: str
    industry: str
    market_cap: int
    country: str
    currency: str
    avg_daily_volume: int
    beta: float
    growth: float
    momentum: float
    quality: float
    value: float
    size: float
    volatility: float
    volatility_1d: float
    volatility_5d: float
    volatility_30d: float
    var_95: float
    cvar_95: float
    tracking_error: float
    sharpe_ratio: float
    information_ratio: float
    max_drawdown: float
    weight: float
    pnl: float

    def to_dict(self) -> Dict:
        """Convert to dictionary for CSV writing"""
        return {
            'timestamp': self.timestamp,
            'symbol': self.symbol,
            'sector': self.sector,
            'industry': self.industry,
            'market_cap': self.market_cap,
            'country': self.country,
            'currency': self.currency,
            'avg_daily_volume': self.avg_daily_volume,
            'beta': self.beta,
            'growth': self.growth,
            'momentum': self.momentum,
            'quality': self.quality,
            'value': self.value,
            'size': self.size,
            'volatility': self.volatility,
            'volatility_1d': self.volatility_1d,
            'volatility_5d': self.volatility_5d,
            'volatility_30d': self.volatility_30d,
            'var_95': self.var_95,
            'cvar_95': self.cvar_95,
            'tracking_error': self.tracking_error,
            'sharpe_ratio': self.sharpe_ratio,
            'information_ratio': self.information_ratio,
            'max_drawdown': self.max_drawdown,
            'weight': self.weight,
            'pnl': self.pnl
        }


@dataclass
class PortfolioRiskSnapshot:
    """Represents portfolio level risk metrics"""
    timestamp: str
    total_exposure: float
    net_exposure: float
    gross_exposure: float
    leverage: float
    concentration: float
    sector_weights: Dict[str, float]
    country_weights: Dict[str, float]
    # New portfolio risk metrics
    portfolio_beta: float = 0.0
    portfolio_var_95: float = 0.0
    portfolio_tracking_error: float = 0.0
    portfolio_sharpe_ratio: float = 0.0
    max_time_to_liquidate: float = 0.0
    avg_time_to_liquidate: float = 0.0
    factor_exposures: Dict[str, float] = field(default_factory=dict)
    correlation_risk: float = 0.0
    concentration_hhi: float = 0.0

    def to_dict(self) -> Dict:
        """Convert to dictionary for CSV writing"""
        base_dict = {
            'timestamp': self.timestamp,
            'total_exposure': self.total_exposure,
            'net_exposure': self.net_exposure,
            'gross_exposure': self.gross_exposure,
            'leverage': self.leverage,
            'concentration': self.concentration,
            'portfolio_beta': self.portfolio_beta,
            'portfolio_var_95': self.portfolio_var_95,
            'portfolio_tracking_error': self.portfolio_tracking_error,
            'portfolio_sharpe_ratio': self.portfolio_sharpe_ratio,
            'max_time_to_liquidate': self.max_time_to_liquidate,
            'avg_time_to_liquidate': self.avg_time_to_liquidate,
            'correlation_risk': self.correlation_risk,
            'concentration_hhi': self.concentration_hhi,
        }

        # Add sector weights with prefix
        for sector, weight in self.sector_weights.items():
            base_dict[f'sector_{sector}'] = weight

        # Add country weights with prefix
        for country, weight in self.country_weights.items():
            base_dict[f'country_{country}'] = weight

        # Add factor exposures with prefix
        for factor, exposure in self.factor_exposures.items():
            base_dict[f'factor_{factor}'] = exposure

        return base_dict


class RiskManager(TrackingManager, CallbackManager):
    """Risk manager with unified storage support"""

    def __init__(self, tracking: bool = False):
        headers = [
            'timestamp', 'symbol', 'sector', 'industry', 'market_cap',
            'country', 'currency', 'avg_daily_volume', 'beta', 'growth',
            'momentum', 'quality', 'value', 'size', 'volatility',
            'volatility_1d', 'volatility_5d', 'volatility_30d',
            'var_95', 'cvar_95', 'tracking_error', 'sharpe_ratio',
            'information_ratio', 'max_drawdown', 'weight', 'pnl'
        ]

        TrackingManager.__init__(
            self,
            manager_name="RiskManager",
            table_name="risk_data",
            headers=headers,
            tracking=tracking
        )
        CallbackManager.__init__(self, "RiskManager")

        self.symbol_risk_data: Dict[str, RiskSnapshot] = {}
        self.portfolio_risk_data: Optional[PortfolioRiskSnapshot] = None

    def evaluate_portfolio_risk(self, timestamp: datetime) -> None:
        """
        Evaluate portfolio risk after minute bar updates are complete.
        Calculate beta, factor exposures, time to liquidate from existing data.
        """
        from source.orchestration.app_state.state_manager import app_state

        if not app_state.portfolio_manager:
            return

        self.logger.info("🎯 PORTFOLIO RISK EVALUATION")

        try:
            # Get current portfolio positions
            positions = app_state.portfolio_manager.get_all_positions()
            if not positions:
                return

            # Get universe data that's already loaded
            universe_data = {}
            if hasattr(app_state, 'universe_manager'):
                universe_data = app_state.universe_manager.get_all_symbols()

            # Calculate total portfolio value
            total_value = sum(abs(float(pos.mtm_value)) for pos in positions.values())
            net_value = sum(float(pos.mtm_value) for pos in positions.values())

            # CREATE SYMBOL-LEVEL RISK DATA for session service
            for symbol, position in positions.items():
                symbol_data = universe_data.get(symbol, {})
                position_weight = float(position.mtm_value) / total_value if total_value > 0 else 0

                # Calculate time to liquidate for this symbol
                position_value = abs(float(position.mtm_value))
                avg_daily_volume = symbol_data.get('avg_daily_volume', 10000000)
                price = float(getattr(position, 'avg_price', 100))
                daily_dollar_volume = avg_daily_volume * price
                days_to_liquidate = position_value / (daily_dollar_volume * 0.20) if daily_dollar_volume > 0 else 999

                # Create a risk snapshot for each symbol
                risk_snapshot = RiskSnapshot(
                    timestamp=timestamp.isoformat(),
                    symbol=symbol,
                    sector=symbol_data.get('sector', 'Technology'),
                    industry=symbol_data.get('industry', 'Technology'),
                    market_cap=symbol_data.get('market_cap', 1000000000),
                    country=symbol_data.get('country', 'US'),
                    currency=symbol_data.get('currency', 'USD'),
                    avg_daily_volume=symbol_data.get('avg_daily_volume', 10000000),
                    beta=symbol_data.get('beta', 1.2),
                    growth=symbol_data.get('exposures', {}).get('growth', 0.1),
                    momentum=symbol_data.get('exposures', {}).get('momentum', 0.05),
                    quality=symbol_data.get('exposures', {}).get('quality', 0.08),
                    value=symbol_data.get('exposures', {}).get('value', -0.02),
                    size=symbol_data.get('exposures', {}).get('size', 0.0),
                    volatility=symbol_data.get('volatility', 0.25),
                    volatility_1d=0.15,
                    volatility_5d=0.20,
                    volatility_30d=0.25,
                    var_95=symbol_data.get('volatility', 0.25) * 1.645,
                    cvar_95=symbol_data.get('volatility', 0.25) * 2.0,
                    tracking_error=symbol_data.get('tracking_error', 0.05),
                    sharpe_ratio=1.0,
                    information_ratio=0.5,
                    max_drawdown=0.15,
                    weight=position_weight,
                    pnl=float(position.unrealized_pnl)
                )
                self.symbol_risk_data[symbol] = risk_snapshot

            # Calculate portfolio beta (weighted average)
            portfolio_beta = 0.0
            total_weight = 0.0

            if total_value > 0:
                for symbol, position in positions.items():
                    weight = abs(float(position.mtm_value)) / total_value
                    symbol_data = universe_data.get(symbol, {})
                    beta = symbol_data.get('beta', 1.0)
                    portfolio_beta += weight * beta
                    total_weight += weight

                portfolio_beta = portfolio_beta / total_weight if total_weight > 0 else 1.0

            # Calculate time to liquidate metrics
            liquidation_times = []
            for symbol, position in positions.items():
                symbol_data = universe_data.get(symbol, {})
                position_value = abs(float(position.mtm_value))
                avg_daily_volume = symbol_data.get('avg_daily_volume', 0)

                if avg_daily_volume > 0:
                    price = float(getattr(position, 'avg_price', 100))
                    daily_dollar_volume = avg_daily_volume * price
                    days_to_liquidate = position_value / (daily_dollar_volume * 0.20)  # 20% participation
                    liquidation_times.append(min(days_to_liquidate, 999))
                else:
                    liquidation_times.append(999)

            max_ttl = max(liquidation_times) if liquidation_times else 0
            avg_ttl = sum(liquidation_times) / len(liquidation_times) if liquidation_times else 0

            # Calculate sector and country weights
            sector_weights = {}
            country_weights = {}
            for symbol, position in positions.items():
                symbol_data = universe_data.get(symbol, {})
                weight = abs(float(position.mtm_value)) / total_value if total_value > 0 else 0

                sector = symbol_data.get('sector', 'Unknown')
                sector_weights[sector] = sector_weights.get(sector, 0) + weight

                country = symbol_data.get('country', 'US')
                country_weights[country] = country_weights.get(country, 0) + weight

            # Calculate factor exposures
            factor_exposures = {
                'growth': 0.0, 'momentum': 0.0, 'quality': 0.0,
                'value': 0.0, 'size': 0.0, 'volatility': 0.0
            }

            for symbol, position in positions.items():
                symbol_data = universe_data.get(symbol, {})
                weight = float(position.mtm_value) / total_value if total_value > 0 else 0
                exposures = symbol_data.get('exposures', {})

                for factor in factor_exposures.keys():
                    factor_exposures[factor] += weight * exposures.get(factor, 0)

            # Calculate concentration HHI
            weights = [abs(float(pos.mtm_value)) / total_value for pos in positions.values()] if total_value > 0 else []
            concentration_hhi = sum(w ** 2 for w in weights)

            # Portfolio VaR (simplified)
            portfolio_var = 0.0
            for symbol, position in positions.items():
                symbol_data = universe_data.get(symbol, {})
                weight = float(position.mtm_value) / total_value if total_value > 0 else 0
                volatility = symbol_data.get('volatility', 0.20)
                var_95 = volatility * 1.645  # 95% confidence
                portfolio_var += (weight ** 2) * (var_95 ** 2)

            portfolio_var_95 = (portfolio_var ** 0.5) if portfolio_var > 0 else 0

            # CREATE OR UPDATE portfolio risk data for session service
            if self.portfolio_risk_data:
                # Update existing data
                self.portfolio_risk_data.portfolio_beta = portfolio_beta
                self.portfolio_risk_data.max_time_to_liquidate = max_ttl
                self.portfolio_risk_data.avg_time_to_liquidate = avg_ttl
                self.portfolio_risk_data.sector_weights = sector_weights
                self.portfolio_risk_data.country_weights = country_weights
                self.portfolio_risk_data.factor_exposures = factor_exposures
                self.portfolio_risk_data.concentration_hhi = concentration_hhi
                self.portfolio_risk_data.portfolio_var_95 = portfolio_var_95
                self.portfolio_risk_data.correlation_risk = max(sector_weights.values()) if sector_weights else 0
                self.portfolio_risk_data.timestamp = timestamp.isoformat()
                self.portfolio_risk_data.total_exposure = total_value
                self.portfolio_risk_data.net_exposure = net_value
                self.portfolio_risk_data.gross_exposure = total_value
            else:
                # Create new portfolio risk data
                self.portfolio_risk_data = PortfolioRiskSnapshot(
                    timestamp=timestamp.isoformat(),
                    total_exposure=total_value,
                    net_exposure=net_value,
                    gross_exposure=total_value,
                    leverage=total_value / abs(net_value) if net_value != 0 else 1.0,
                    concentration=max(weights) if weights else 0,
                    sector_weights=sector_weights,
                    country_weights=country_weights,
                    portfolio_beta=portfolio_beta,
                    portfolio_var_95=portfolio_var_95,
                    portfolio_tracking_error=0.05,
                    portfolio_sharpe_ratio=1.0,
                    max_time_to_liquidate=max_ttl,
                    avg_time_to_liquidate=avg_ttl,
                    factor_exposures=factor_exposures,
                    correlation_risk=max(sector_weights.values()) if sector_weights else 0,
                    concentration_hhi=concentration_hhi
                )

            self.logger.info(f"Portfolio Beta: {portfolio_beta:.3f}, Max TTL: {max_ttl:.1f} days, "
                             f"Symbols: {len(self.symbol_risk_data)}, HHI: {concentration_hhi:.3f}")

        except Exception as e:
            self.logger.error(f"Error in portfolio risk evaluation: {e}")
            import traceback
            self.logger.error(f"Risk evaluation traceback: {traceback.format_exc()}")

    def _prepare_symbol_risk_data(self) -> List[Dict]:
        """Prepare symbol risk data for storage"""
        return [snapshot.to_dict() for snapshot in self.symbol_risk_data.values()]

    def _prepare_portfolio_risk_data(self) -> Optional[Dict]:
        """Prepare portfolio risk data for storage"""
        if self.portfolio_risk_data:
            return self.portfolio_risk_data.to_dict()
        return None

    def update_from_risk_holdings(self, risk_holdings, timestamp: datetime) -> None:
        """Update risk data from RiskHoldings protobuf message"""
        with self._lock:
            try:
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp)

                # Process symbol level risk data
                for symbol_data in risk_holdings.symbols:
                    risk_snapshot = RiskSnapshot(
                        timestamp=timestamp.isoformat(),
                        symbol=symbol_data.data.symbol,
                        sector=symbol_data.data.sector,
                        industry=symbol_data.data.industry,
                        market_cap=symbol_data.data.market_cap,
                        country=symbol_data.data.country,
                        currency=symbol_data.data.currency,
                        avg_daily_volume=symbol_data.data.avg_daily_volume,
                        beta=symbol_data.data.beta,
                        growth=symbol_data.exposures.growth,
                        momentum=symbol_data.exposures.momentum,
                        quality=symbol_data.exposures.quality,
                        value=symbol_data.exposures.value,
                        size=symbol_data.exposures.size,
                        volatility=symbol_data.metrics.volatility,
                        volatility_1d=symbol_data.metrics.volatility_1d,
                        volatility_5d=symbol_data.metrics.volatility_5d,
                        volatility_30d=symbol_data.metrics.volatility_30d,
                        var_95=symbol_data.metrics.var_95,
                        cvar_95=symbol_data.metrics.cvar_95,
                        tracking_error=symbol_data.metrics.tracking_error,
                        sharpe_ratio=symbol_data.metrics.sharpe_ratio,
                        information_ratio=symbol_data.metrics.information_ratio,
                        max_drawdown=symbol_data.metrics.max_drawdown,
                        weight=symbol_data.weight,
                        pnl=symbol_data.pnl
                    )
                    self.symbol_risk_data[symbol_data.data.symbol] = risk_snapshot

                # Process portfolio level metrics
                portfolio_metrics = risk_holdings.portfolio_metrics
                self.portfolio_risk_data = PortfolioRiskSnapshot(
                    timestamp=timestamp.isoformat(),
                    total_exposure=portfolio_metrics.total_exposure,
                    net_exposure=portfolio_metrics.net_exposure,
                    gross_exposure=portfolio_metrics.gross_exposure,
                    leverage=portfolio_metrics.leverage,
                    concentration=portfolio_metrics.concentration,
                    sector_weights=dict(portfolio_metrics.sector_weights),
                    country_weights=dict(portfolio_metrics.country_weights)
                )

                # Write to storage
                if self.tracking:
                    # Write symbol data
                    symbol_data = self._prepare_symbol_risk_data()
                    if symbol_data:
                        self.write_to_storage(symbol_data, timestamp=timestamp)

                    # Write portfolio data to separate table
                    portfolio_data = self._prepare_portfolio_risk_data()
                    if portfolio_data:
                        # Create a separate tracking manager for portfolio risk
                        portfolio_headers = [
                            'timestamp', 'total_exposure', 'net_exposure', 'gross_exposure',
                            'leverage', 'concentration', 'portfolio_beta', 'portfolio_var_95',
                            'portfolio_tracking_error', 'portfolio_sharpe_ratio',
                            'max_time_to_liquidate', 'avg_time_to_liquidate',
                            'correlation_risk', 'concentration_hhi'
                        ]

                        # Add dynamic sector and country columns
                        if portfolio_data.get('sector_weights'):
                            for sector in portfolio_data['sector_weights'].keys():
                                portfolio_headers.append(f'sector_{sector}')
                        if portfolio_data.get('country_weights'):
                            for country in portfolio_data['country_weights'].keys():
                                portfolio_headers.append(f'country_{country}')

                        # Add factor exposure columns
                        if portfolio_data.get('factor_exposures'):
                            for factor in portfolio_data['factor_exposures'].keys():
                                portfolio_headers.append(f'factor_{factor}')

                        # Create temporary manager for portfolio risk
                        from source.simulation.managers.utils import TrackingManager
                        portfolio_manager = TrackingManager(
                            manager_name="PortfolioRiskManager",
                            table_name="portfolio_risk_data",
                            headers=portfolio_headers,
                            tracking=self.tracking
                        )
                        portfolio_manager.write_to_storage([portfolio_data], timestamp=timestamp)

                # Use tuple for callback
                callback_data = (self.symbol_risk_data.copy(), self.portfolio_risk_data)
                self._notify_callbacks(callback_data)

            except Exception as e:
                self.logger.error(f"Error updating risk data: {e}")
                raise

    def get_symbol_risk(self, symbol: str) -> Optional[RiskSnapshot]:
        """Get risk data for a specific symbol"""
        with self._lock:
            return self.symbol_risk_data.get(symbol)

    def get_all_symbol_risk(self) -> Dict[str, RiskSnapshot]:
        """Get risk data for all symbols"""
        with self._lock:
            return self.symbol_risk_data.copy()

    def get_portfolio_risk(self) -> Optional[PortfolioRiskSnapshot]:
        """Get portfolio level risk metrics"""
        with self._lock:
            return self.portfolio_risk_data

    def register_update_callback(self, callback: Callable) -> None:
        """Alias for register_callback to maintain compatibility"""
        self.register_callback(callback)