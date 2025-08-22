# source/orchestration/servers/session/state_managers/trade_state_manager.py
"""
Trade State Management Component
Extracted from session_server_impl.py to reduce file size
"""

import logging
from dateutil.parser import parse
import traceback
from source.api.grpc.session_exchange_interface_pb2 import ExchangeDataUpdate, Trade


class TradeStateManager:
    """Handles trade state operations for session server"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_current_trades_state(self, update: ExchangeDataUpdate):
        """Poll current trades state - FIXED to handle dictionary data"""
        from source.orchestration.app_state.state_manager import app_state

        try:
            # Get trade_manager first
            if not app_state.trade_manager:
                print(f"🔥🔥🔥 COMPOSITE STATE: No trade_manager available")
                return

            # Get all trades from memory (they are stored as dictionaries)
            trades = app_state.trade_manager.get_all_trades()
            print(f"🔥🔥🔥 COMPOSITE STATE: Found {len(trades)} trades from trade_manager")

            for trade_id, trade_dict in trades.items():
                print(f"🔥🔥🔥 COMPOSITE STATE: Trade {trade_id} data: {trade_dict}")

                trade_data = Trade()

                # FIXED: Access dictionary keys instead of object attributes
                trade_data.trade_id = trade_dict.get('trade_id', '')
                trade_data.order_id = trade_dict.get('order_id', '')
                trade_data.cl_order_id = trade_dict.get('cl_order_id', '')
                trade_data.symbol = trade_dict.get('symbol', '')
                trade_data.side = str(trade_dict.get('side', ''))
                trade_data.currency = trade_dict.get('currency', 'USD')
                trade_data.price = float(trade_dict.get('price', 0.0))
                trade_data.quantity = float(trade_dict.get('quantity', 0.0))
                trade_data.detail = trade_dict.get('detail', '')

                # Handle timestamps - they can be datetime objects or strings
                start_timestamp = trade_dict.get('start_timestamp')
                end_timestamp = trade_dict.get('end_timestamp')

                if start_timestamp:
                    if isinstance(start_timestamp, str):
                        start_dt = parse(start_timestamp)
                        trade_data.start_timestamp = int(start_dt.timestamp() * 1000)
                    else:
                        # It's a datetime object
                        trade_data.start_timestamp = int(start_timestamp.timestamp() * 1000)

                if end_timestamp:
                    if isinstance(end_timestamp, str):
                        end_dt = parse(end_timestamp)
                        trade_data.end_timestamp = int(end_dt.timestamp() * 1000)
                    else:
                        # It's a datetime object
                        trade_data.end_timestamp = int(end_timestamp.timestamp() * 1000)

                # Use end_timestamp as the main timestamp for compatibility
                if hasattr(trade_data, 'timestamp'):
                    trade_data.timestamp = trade_data.end_timestamp

                update.trades.append(trade_data)
                print(f"🔥🔥🔥 COMPOSITE STATE: Added trade {trade_data.trade_id} for order {trade_data.order_id}")
                print(
                    f"🔥🔥🔥 COMPOSITE STATE: Trade details - {trade_data.symbol} {trade_data.side} {trade_data.quantity}@${trade_data.price}")

            print(f"🔥🔥🔥 COMPOSITE STATE: Trades FINAL - {len(trades)} trades added from memory")
            self.logger.debug(f"💰 Added {len(trades)} trades to update")

        except Exception as e:
            print(f"🔥🔥🔥 COMPOSITE STATE: Error adding trades state: {e}")
            print(f"🔥🔥🔥 COMPOSITE STATE: Trade error traceback: {traceback.format_exc()}")
            self.logger.error(f"Error adding trades state: {e}")