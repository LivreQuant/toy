# source/simulation/managers/trade.py
from typing import Dict, List, Optional
from source.simulation.managers.utils import TrackingManager


class TradeManager(TrackingManager):
    def __init__(self, tracking: bool = False):
        headers = [
            'start_timestamp', 'end_timestamp', 'trade_id', 'order_id',
            'cl_order_id', 'symbol', 'side', 'currency', 'price', 'quantity',
            'detail'
        ]

        super().__init__(
            manager_name="TradeManager",
            table_name="trade_data",
            headers=headers,
            tracking=tracking
        )

        self._trades: Dict[str, Dict] = {}
        self._order_trades: Dict[str, List[str]] = {}

    def _prepare_trade_data(self, trade_data: Dict) -> List[Dict]:
        """Prepare trade data for storage"""

        return [{
            'start_timestamp': trade_data.get('start_timestamp'),  # Keep as datetime
            'end_timestamp': trade_data.get('end_timestamp'),      # Keep as datetime
            'trade_id': trade_data.get('trade_id', ''),
            'order_id': trade_data.get('order_id', ''),
            'cl_order_id': trade_data.get('cl_order_id', ''),
            'symbol': trade_data.get('symbol', ''),
            'side': trade_data.get('side', ''),
            'currency': trade_data.get('currency', ''),
            'price': trade_data.get('price', 0.0),
            'quantity': trade_data.get('quantity', 0),
            'detail': trade_data.get('detail', '')
        }]

    def add_trade(self, trade_data: Dict) -> None:
        """Add trade to in-memory storage and persist"""
        with self._lock:
            trade_id = trade_data['trade_id']
            order_id = trade_data['order_id']

            # Store in memory
            self._trades[trade_id] = trade_data
            if order_id not in self._order_trades:
                self._order_trades[order_id] = []
            self._order_trades[order_id].append(trade_id)

            # Persist to storage (file or database based on config)
            if self.tracking:
                trade_row = self._prepare_trade_data(trade_data)
                self.write_to_storage(trade_row)

    def get_trade(self, trade_id: str) -> Optional[Dict]:
        """Get a specific trade"""
        with self._lock:
            return self._trades.get(trade_id)

    def get_trades_for_order(self, order_id: str) -> List[Dict]:
        """Get all trades for a specific order"""
        with self._lock:
            trade_ids = self._order_trades.get(order_id, [])
            return [self._trades[tid] for tid in trade_ids if tid in self._trades]

    def get_all_trades(self) -> Dict[str, Dict]:
        """Get all trades"""
        with self._lock:
            return self._trades.copy()