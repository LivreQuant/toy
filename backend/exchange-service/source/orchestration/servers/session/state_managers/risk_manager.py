# source/orchestration/servers/session/state_managers/risk_state_manager.py
"""
Risk State Management Component
Extracted from session_server_impl.py to reduce file size
"""

import logging
from source.proto.session_exchange_interface_pb2 import (
    ExchangeDataUpdate, RiskStatus, EquityRiskData, PortfolioRiskData,
    RiskExposures, RiskMetrics
)


# RISK INCLUDES PORTFOLIO AGGREGATE RISK + SYMBOL RISK

class RiskStateManager:
    """Handles risk state operations for session server"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_current_risk_state(self, update: ExchangeDataUpdate):
        """Poll current risk state - Fixed for proto"""
        from source.orchestration.app_state.state_manager import app_state
        if not app_state.risk_manager:
            return

        try:
            symbol_risk_data = app_state.risk_manager.get_all_symbol_risk()
            portfolio_risk_data = app_state.risk_manager.get_portfolio_risk()

            update.risk.CopyFrom(self.build_risk_status(symbol_risk_data, portfolio_risk_data))
            self.logger.debug(f"📊 Added risk data with {len(symbol_risk_data)} symbols to update")
        except Exception as e:
            self.logger.error(f"Error adding risk state: {e}")

    def build_risk_status(self, symbol_risk_data, portfolio_risk_data) -> RiskStatus:
        """Build risk status from risk data - Fixed for proto"""
        risk_status = RiskStatus()

        # Add symbol risk data
        for symbol, risk_data in symbol_risk_data.items():
            equity_risk = EquityRiskData()
            equity_risk.symbol = symbol
            equity_risk.sector = getattr(risk_data, 'sector', '')
            equity_risk.industry = getattr(risk_data, 'industry', '')
            equity_risk.market_cap = float(getattr(risk_data, 'market_cap', 0.0))
            equity_risk.country = getattr(risk_data, 'country', '')
            equity_risk.currency = getattr(risk_data, 'currency', 'USD')
            equity_risk.avg_daily_volume = float(getattr(risk_data, 'avg_daily_volume', 0.0))
            equity_risk.beta = float(getattr(risk_data, 'beta', 0.0))
            equity_risk.weight = float(getattr(risk_data, 'weight', 0.0))
            equity_risk.pnl = float(getattr(risk_data, 'pnl', 0.0))

            # Add exposures
            if hasattr(risk_data, 'exposures'):
                exposures = RiskExposures()
                exposures.growth = float(getattr(risk_data.exposures, 'growth', 0.0))
                exposures.momentum = float(getattr(risk_data.exposures, 'momentum', 0.0))
                exposures.quality = float(getattr(risk_data.exposures, 'quality', 0.0))
                exposures.value = float(getattr(risk_data.exposures, 'value', 0.0))
                exposures.size = float(getattr(risk_data.exposures, 'size', 0.0))
                exposures.volatility = float(getattr(risk_data.exposures, 'volatility', 0.0))
                equity_risk.exposures.CopyFrom(exposures)

            # Add risk metrics
            if hasattr(risk_data, 'risk_metrics'):
                metrics = RiskMetrics()
                metrics.volatility_1d = float(getattr(risk_data.risk_metrics, 'volatility_1d', 0.0))
                metrics.volatility_5d = float(getattr(risk_data.risk_metrics, 'volatility_5d', 0.0))
                metrics.volatility_30d = float(getattr(risk_data.risk_metrics, 'volatility_30d', 0.0))
                metrics.var_95 = float(getattr(risk_data.risk_metrics, 'var_95', 0.0))
                metrics.cvar_95 = float(getattr(risk_data.risk_metrics, 'cvar_95', 0.0))
                metrics.tracking_error = float(getattr(risk_data.risk_metrics, 'tracking_error', 0.0))
                metrics.sharpe_ratio = float(getattr(risk_data.risk_metrics, 'sharpe_ratio', 0.0))
                metrics.information_ratio = float(getattr(risk_data.risk_metrics, 'information_ratio', 0.0))
                metrics.max_drawdown = float(getattr(risk_data.risk_metrics, 'max_drawdown', 0.0))
                equity_risk.risk_metrics.CopyFrom(metrics)

            risk_status.symbols.append(equity_risk)

        # Add portfolio risk data
        if portfolio_risk_data:
            portfolio_risk = PortfolioRiskData()
            portfolio_risk.net_exposure = float(getattr(portfolio_risk_data, 'net_exposure', 0.0))
            portfolio_risk.gross_exposure = float(getattr(portfolio_risk_data, 'gross_exposure', 0.0))
            portfolio_risk.leverage = float(getattr(portfolio_risk_data, 'leverage', 0.0))
            portfolio_risk.concentration = float(getattr(portfolio_risk_data, 'concentration', 0.0))

            # Add sector weights
            if hasattr(portfolio_risk_data, 'sector_weights'):
                for sector, weight in portfolio_risk_data.sector_weights.items():
                    portfolio_risk.sector_weights[sector] = float(weight)

            # Add country weights
            if hasattr(portfolio_risk_data, 'country_weights'):
                for country, weight in portfolio_risk_data.country_weights.items():
                    portfolio_risk.country_weights[country] = float(weight)

            risk_status.portfolio_metrics.CopyFrom(portfolio_risk)

        return risk_status
