# source/simulation/managers/order_view.py
from typing import Dict, Optional, List
from datetime import datetime
from dataclasses import dataclass
from source.simulation.managers.utils import TrackingManager
from source.utils.timezone_utils import to_iso_string


@dataclass
class OrderViewEvent:
    """Represents an order state"""
    timestamp: str
    order_id: str
    cl_order_id: str
    symbol: str
    side: str
    original_qty: float
    remaining_qty: float
    completed_qty: float
    currency: str
    price: float
    order_type: str
    participation_rate: float
    submit_timestamp: str
    start_timestamp: str
    state: str
    trades: List[Dict]
    cancel_timestamp: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for CSV writing"""

        data = {
            'timestamp': to_iso_string(self.timestamp) if isinstance(self.timestamp, datetime) else self.timestamp,
            'order_id': self.order_id,
            'cl_order_id': self.cl_order_id,
            'symbol': self.symbol,
            'side': self.side,
            'original_qty': self.original_qty,
            'remaining_qty': self.remaining_qty,
            'completed_qty': self.completed_qty,
            'currency': self.currency,
            'price': self.price,
            'order_type': self.order_type,
            'participation_rate': self.participation_rate,
            'submit_timestamp': self.submit_timestamp,
            'start_timestamp': self.start_timestamp,
            'state': self.state
        }
        if self.cancel_timestamp:
            data['cancel_timestamp'] = self.cancel_timestamp
        return data


class OrderViewManager(TrackingManager):
    def __init__(self, tracking: bool = False):
        headers = [
            'timestamp', 'order_id', 'cl_order_id', 'symbol', 'side',
            'original_qty', 'remaining_qty', 'completed_qty', 'currency', 'price', 'order_type',
            'participation_rate', 'submit_timestamp', 'start_timestamp', 'state', 'cancel_timestamp'
        ]

        super().__init__(
            manager_name="OrderViewManager",
            table_name="order_view",
            headers=headers,
            tracking=tracking
        )

        self.orders_view: Dict[str, OrderViewEvent] = {}

    def _prepare_order_view_data(self) -> List[Dict]:
        """Prepare order view data for storage"""
        snapshot_data = []
        with self._lock:
            for order in self.orders_view.values():
                snapshot_data.append(order.to_dict())
        return snapshot_data

    def update_orders_view(self, timestamp: datetime) -> None:
        """Add or update an order"""
        with self._lock:
            from source.orchestration.app_state.state_manager import app_state

            if app_state.order_manager:
                orders = app_state.order_manager.get_all_orders()

            for order in orders.values():
                trades = app_state.trade_manager.get_trades_for_order(order.order_id)

                completed_qty = sum(float(trade['quantity']) for trade in trades)
                remaining_qty = order.original_qty - completed_qty

                state = 'WORKING'
                if completed_qty >= order.original_qty:
                    state = 'COMPLETED'
                    remaining_qty = 0.0
                    completed_qty = order.original_qty
                elif order.cancelled:
                    state = 'CANCELLED'
                    remaining_qty = 0.0

                order_view = OrderViewEvent(
                    timestamp=timestamp.isoformat(),
                    order_id=order.order_id,
                    cl_order_id=order.cl_order_id,
                    symbol=order.symbol,
                    side=order.side,
                    original_qty=order.original_qty,
                    remaining_qty=remaining_qty,
                    completed_qty=completed_qty,
                    currency=order.currency,
                    price=order.price,
                    order_type=order.order_type,
                    participation_rate=order.participation_rate,
                    submit_timestamp=order.submit_timestamp.isoformat() if isinstance(order.submit_timestamp, datetime) else order.submit_timestamp,
                    start_timestamp=order.start_timestamp.isoformat() if isinstance(order.start_timestamp, datetime) else order.start_timestamp,
                    state=state,
                    trades=trades,
                    cancel_timestamp=order.cancel_timestamp.isoformat() if order.cancel_timestamp else None
                )

                self.orders_view[order_view.order_id] = order_view

            if self.tracking:
                data = self._prepare_order_view_data()
                self.write_to_storage(data, timestamp=timestamp)

    def get_order(self, order_id: str) -> Optional[OrderViewEvent]:
        """Get a specific order"""
        with self._lock:
            return self.orders_view.get(order_id)

    def get_all_orders(self) -> Dict[str, OrderViewEvent]:
        """Get all current orders"""
        with self._lock:
            return self.orders_view.copy()