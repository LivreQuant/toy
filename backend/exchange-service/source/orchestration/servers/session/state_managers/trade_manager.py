# source/orchestration/servers/session/state_managers/trade_state_manager.py
"""
Trade State Management Component
Extracted from session_server_impl.py to reduce file size
"""

import logging
from source.api.grpc.session_exchange_interface_pb2 import ExchangeDataUpdate, Trade


class TradeStateManager:
    """Handles trade state operations for session server"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_current_trades_state(self, update: ExchangeDataUpdate):
        """Poll current trades state - Fixed for proto"""
        from source.orchestration.app_state.state_manager import app_state
        if not app_state.order_manager:
            return

        try:
            # Fix: Use correct method name
            if hasattr(app_state.order_manager, 'get_all_trades'):
                trades = app_state.order_manager.get_all_trades()
            elif hasattr(app_state.order_manager, 'trades'):
                trades = app_state.order_manager.trades
            elif hasattr(app_state, 'trade_manager') and app_state.trade_manager:
                trades = app_state.trade_manager.get_all_trades() if hasattr(app_state.trade_manager,
                                                                             'get_all_trades') else []
            else:
                trades = []

            for trade in trades:
                trade_data = Trade()
                trade_data.trade_id = getattr(trade, 'trade_id', '')
                trade_data.order_id = getattr(trade, 'order_id', '')
                trade_data.cl_order_id = getattr(trade, 'cl_order_id', '')
                trade_data.symbol = getattr(trade, 'symbol', '')

                # Fix: Handle side enum properly
                side = getattr(trade, 'side', '')
                if hasattr(side, 'value'):
                    trade_data.side = side.value
                else:
                    trade_data.side = str(side)

                trade_data.currency = getattr(trade, 'currency', 'USD')
                trade_data.price = float(getattr(trade, 'price', 0.0))
                trade_data.quantity = float(getattr(trade, 'quantity', 0.0))
                trade_data.remaining_qty = float(getattr(trade, 'remaining_qty', 0.0))
                trade_data.completed_qty = float(getattr(trade, 'completed_qty', 0.0))
                trade_data.detail = getattr(trade, 'detail', '')

                # Fix: Timestamps
                timestamp = getattr(trade, 'timestamp', None)
                if timestamp:
                    trade_data.start_timestamp = int(timestamp.timestamp() * 1000)
                    trade_data.end_timestamp = int(timestamp.timestamp() * 1000)

                update.trades.append(trade_data)

            self.logger.debug(f"💰 Added {len(trades)} trades to update")
        except Exception as e:
            self.logger.error(f"Error adding trades state: {e}")