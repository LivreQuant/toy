# source/orchestration/servers/session/state_managers/risk_manager.py
"""
Risk State Management Component
Extracted from session_server_impl.py to reduce file size
"""

import traceback
import logging
from source.api.grpc.session_exchange_interface_pb2 import (
    ExchangeDataUpdate, RiskStatus, EquityRiskData, PortfolioRiskData,
    RiskExposures, RiskMetrics
)


class RiskStateManager:
    """Handles risk state operations for session server"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_current_risk_state(self, update: ExchangeDataUpdate):
        """Poll current risk state - Fixed for proto"""
        from source.orchestration.app_state.state_manager import app_state
        if not app_state.risk_manager:
            print(f"🔥🔥🔥 COMPOSITE STATE: No risk_manager available")
            return

        try:
            symbol_risk_data = app_state.risk_manager.get_all_symbol_risk()
            portfolio_risk_data = app_state.risk_manager.get_portfolio_risk()

            print(f"🔥🔥🔥 COMPOSITE STATE: Found {len(symbol_risk_data)} symbol risk data")
            print(f"🔥🔥🔥 COMPOSITE STATE: Portfolio risk data: {portfolio_risk_data is not None}")

            if portfolio_risk_data:
                print(f"🔥🔥🔥 COMPOSITE STATE: Portfolio Beta: {getattr(portfolio_risk_data, 'portfolio_beta', 'N/A')}")

            update.risk.CopyFrom(self.build_risk_status(symbol_risk_data, portfolio_risk_data))
            self.logger.debug(f"📊 Added risk data with {len(symbol_risk_data)} symbols to update")
            print(f"🔥🔥🔥 COMPOSITE STATE: Risk data added to update")
        except Exception as e:
            print(f"🔥🔥🔥 COMPOSITE STATE: Error adding risk state: {e}")
            self.logger.error(f"Error adding risk state: {e}")
            print(f"🔥🔥🔥 COMPOSITE STATE: Traceback: {traceback.format_exc()}")

    def build_risk_status(self, symbol_risk_data, portfolio_risk_data) -> RiskStatus:
        """Build risk status from risk data - Fixed for actual protobuf fields"""
        risk_status = RiskStatus()

        # Add symbol risk data - FIXED to match actual protobuf fields
        for symbol, risk_data in symbol_risk_data.items():
            equity_risk = EquityRiskData()
            equity_risk.symbol = symbol
            # FIXED: EquityRiskData only has: symbol, var, expected_shortfall, currency
            equity_risk.var = getattr(risk_data, 'var_95', 0.0)
            equity_risk.expected_shortfall = getattr(risk_data, 'cvar_95', 0.0)
            equity_risk.currency = getattr(risk_data, 'currency', 'USD')

            risk_status.equity_risk.append(equity_risk)

        # Add portfolio risk data - FIXED to match actual protobuf fields
        if portfolio_risk_data:
            portfolio_risk = PortfolioRiskData()
            # FIXED: PortfolioRiskData only has: portfolio_var, portfolio_expected_shortfall, currency
            portfolio_risk.portfolio_var = getattr(portfolio_risk_data, 'portfolio_var_95', 0.0)
            portfolio_risk.portfolio_expected_shortfall = portfolio_risk.portfolio_var * 1.3  # Rough estimate
            portfolio_risk.currency = 'USD'

            risk_status.portfolio_risk.CopyFrom(portfolio_risk)

        # Add exposures - sector and country weights
        if portfolio_risk_data:
            exposures = RiskExposures()

            # Add sector exposures
            sector_weights = getattr(portfolio_risk_data, 'sector_weights', {})
            for sector, weight in sector_weights.items():
                exposures.sector_exposures[sector] = float(weight)

            # Add country exposures
            country_weights = getattr(portfolio_risk_data, 'country_weights', {})
            for country, weight in country_weights.items():
                exposures.country_exposures[country] = float(weight)

            risk_status.exposures.CopyFrom(exposures)

        # Add metrics - portfolio beta and other metrics
        if portfolio_risk_data:
            metrics = RiskMetrics()
            metrics.beta = getattr(portfolio_risk_data, 'portfolio_beta', 1.0)
            metrics.alpha = 0.0  # Default
            metrics.sharpe_ratio = getattr(portfolio_risk_data, 'portfolio_sharpe_ratio', 0.0)
            metrics.sortino_ratio = metrics.sharpe_ratio * 1.2  # Rough estimate

            risk_status.metrics.CopyFrom(metrics)

        # Add symbols list
        for symbol in symbol_risk_data.keys():
            risk_status.symbols.append(symbol)

        return risk_status