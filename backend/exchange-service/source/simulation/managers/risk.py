# source/simulation/managers/risk.py
from threading import RLock
from typing import Dict, Optional, List, Callable, Tuple, TYPE_CHECKING
from datetime import datetime
from dataclasses import dataclass
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

    def to_dict(self) -> Dict:
        """Convert to dictionary for CSV writing"""
        base_dict = {
            'timestamp': self.timestamp,
            'total_exposure': self.total_exposure,
            'net_exposure': self.net_exposure,
            'gross_exposure': self.gross_exposure,
            'leverage': self.leverage,
            'concentration': self.concentration,
        }

        # Add sector weights with prefix
        for sector, weight in self.sector_weights.items():
            base_dict[f'sector_{sector}'] = weight

        # Add country weights with prefix
        for country, weight in self.country_weights.items():
            base_dict[f'country_{country}'] = weight

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
                        # source/simulation/managers/risk.py (continued)
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
                            'leverage', 'concentration'
                        ]
                        # Add dynamic sector and country columns
                        if 'sector_weights' in portfolio_data:
                            for sector in portfolio_data['sector_weights'].keys():
                                portfolio_headers.append(f'sector_{sector}')
                        if 'country_weights' in portfolio_data:
                            for country in portfolio_data['country_weights'].keys():
                                portfolio_headers.append(f'country_{country}')

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