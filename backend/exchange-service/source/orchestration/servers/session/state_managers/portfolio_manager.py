# source/orchestration/servers/session/state_managers/portfolio_state_manager.py
"""
Portfolio State Management Component
Extracted from session_server_impl.py to reduce file size
"""

import logging
from source.api.grpc.session_exchange_interface_pb2 import ExchangeDataUpdate, PortfolioStatus, Position


class PortfolioStateManager:
    """Handles portfolio state operations for session server"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_current_portfolio_state(self, update: ExchangeDataUpdate):
        """Poll current portfolio state - Fixed for proto"""
        from source.orchestration.app_state.state_manager import app_state
        if not app_state.portfolio_manager:
            return

        try:
            positions = app_state.portfolio_manager.get_all_positions()
            update.portfolio.CopyFrom(self.build_portfolio_status(positions))
            self.logger.debug(f"💼 Added portfolio with {len(positions)} positions to update")
        except Exception as e:
            self.logger.error(f"Error adding portfolio state: {e}")

    def build_portfolio_status(self, positions) -> PortfolioStatus:
        """Build portfolio status from positions - FIXED for mtm_value"""
        portfolio_status = PortfolioStatus()

        total_value = 0.0
        total_pnl = 0.0
        unrealized_pnl = 0.0
        realized_pnl = 0.0

        for position in positions.values():
            print(
                f"🔥🔥🔥 COMPOSITE STATE: Position {position.symbol} attributes: {[attr for attr in dir(position) if not attr.startswith('_')]}")

            pos = Position()
            pos.symbol = getattr(position, 'symbol', '')
            pos.quantity = float(getattr(position, 'quantity', 0.0))
            pos.target_quantity = float(getattr(position, 'target_quantity', 0.0))
            pos.currency = getattr(position, 'currency', 'USD')

            # FIXED: Use correct field name for average price
            if hasattr(position, 'avg_price'):
                pos.average_cost = float(position.avg_price)
            elif hasattr(position, 'average_price'):
                pos.average_cost = float(position.average_price)
            elif hasattr(position, 'price'):
                pos.average_cost = float(position.price)
            else:
                pos.average_cost = 0.0

            # CRITICAL FIX: Use mtm_value instead of market_value
            market_value = 0.0
            if hasattr(position, 'mtm_value'):
                market_value = float(position.mtm_value)
                print(f"🔥🔥🔥 COMPOSITE STATE: Found mtm_value for {position.symbol}: ${market_value}")
            elif hasattr(position, 'market_value'):
                market_value = float(position.market_value)
                print(f"🔥🔥🔥 COMPOSITE STATE: Found market_value for {position.symbol}: ${market_value}")
            else:
                print(f"🔥🔥🔥 COMPOSITE STATE: No market/mtm value found for {position.symbol}")

            pos.market_value = market_value

            pos.sod_realized_pnl = float(getattr(position, 'sod_realized_pnl', 0.0))
            pos.itd_realized_pnl = float(getattr(position, 'itd_realized_pnl', 0.0))
            pos.realized_pnl = float(getattr(position, 'realized_pnl', 0.0))
            pos.unrealized_pnl = float(getattr(position, 'unrealized_pnl', 0.0))

            portfolio_status.positions.append(pos)

            total_value += pos.market_value
            unrealized_pnl += pos.unrealized_pnl
            realized_pnl += pos.realized_pnl

        total_pnl = unrealized_pnl + realized_pnl

        portfolio_status.cash_balance = 0.0
        portfolio_status.total_value = total_value
        portfolio_status.total_pnl = total_pnl
        portfolio_status.unrealized_pnl = unrealized_pnl
        portfolio_status.realized_pnl = realized_pnl

        print(f"🔥🔥🔥 COMPOSITE STATE: Portfolio FINAL - total_value=${total_value}, unrealized_pnl=${unrealized_pnl}")

        return portfolio_status