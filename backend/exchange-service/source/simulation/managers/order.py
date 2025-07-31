# source/simulation/managers/order.py
import os
import csv
import logging
from typing import Dict, Optional, List, Callable
from datetime import datetime
from dataclasses import dataclass

from source.simulation.managers.utils import TrackingManager, CallbackManager


@dataclass
class Order:
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
    submit_timestamp: datetime
    start_timestamp: datetime
    cancelled: bool = False
    cancel_timestamp: Optional[datetime] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for CSV writing"""
        from source.utils.timezone_utils import to_iso_string

        return {
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
            'submit_timestamp': to_iso_string(self.submit_timestamp),
            'start_timestamp': to_iso_string(self.start_timestamp),
            'cancelled': self.cancelled,
            'cancel_timestamp': to_iso_string(self.cancel_timestamp) if self.cancel_timestamp else None
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Order':
        """Create Order from dictionary"""
        return cls(
            order_id=data['order_id'],
            cl_order_id=data.get('cl_order_id', ''),
            symbol=data['symbol'],
            side=data['side'],
            original_qty=float(data.get('original_qty', 0)),
            remaining_qty=float(data.get('remaining_qty', 0)),
            completed_qty=float(data.get('completed_qty', 0)),
            currency=data.get('currency', 'USD'),
            price=float(data.get('price', 0)),
            order_type=data.get('order_type', ''),
            participation_rate=float(data.get('participation_rate', 0)),
            submit_timestamp=data['submit_timestamp'] if isinstance(data['submit_timestamp'],
                                                                    datetime) else datetime.fromisoformat(
                data['submit_timestamp']),
            start_timestamp=data.get('start_timestamp', data['submit_timestamp']) if isinstance(
                data.get('start_timestamp', data['submit_timestamp']), datetime) else datetime.fromisoformat(
                data.get('start_timestamp', data['submit_timestamp'])),
            cancelled=data.get('cancelled', False),
            cancel_timestamp=datetime.fromisoformat(data['cancel_timestamp']) if data.get('cancel_timestamp') else None
        )


class OrderManager(TrackingManager, CallbackManager):
    def __init__(self, tracking: bool = False):
        headers = [
            'timestamp', 'event_type', 'order_id', 'cl_order_id',
            'symbol', 'side', 'original_qty', 'remaining_qty', 'completed_qty', 'currency', 'price',
            'order_type', 'participation_rate'
        ]

        TrackingManager.__init__(
            self,
            manager_name="OrderManager",
            table_name="order_data",
            headers=headers,
            tracking=tracking
        )
        CallbackManager.__init__(self, "OrderManager")

        self._orders: Dict[str, Order] = {}

    def initialize_orders(self, orders: Dict[str, Dict], timestamp: datetime) -> None:
        """Initialize orders from last snapshot - no SOD file writing"""
        with self._lock:
            self._orders = {
                order_id: Order.from_dict(order_data)
                for order_id, order_data in orders.items()
            }

        self._notify_callbacks(self._orders.copy())

    def _prepare_order_entry(self, data: Dict, event_type: str, cancel_timestamp: Optional[datetime] = None) -> Dict:
        from source.utils.timezone_utils import to_iso_string, ensure_timezone_aware

        timestamp_str = None
        if cancel_timestamp and event_type == "CANCELLED":
            timestamp_str = to_iso_string(cancel_timestamp)
        else:
            submit_time = data.get('submit_timestamp')
            if isinstance(submit_time, datetime):
                timestamp_str = to_iso_string(submit_time)
            else:
                timestamp_str = submit_time

        if not timestamp_str:
            raise ValueError("No timestamp found in order data")

        return {
            'timestamp': timestamp_str,
            'event_type': event_type,
            'order_id': data.get('order_id', ''),
            'cl_order_id': data.get('cl_order_id', ''),
            'symbol': data.get('symbol', ''),
            'side': data.get('side', ''),
            'original_qty': data.get('original_qty', 0.0),
            'remaining_qty': data.get('remaining_qty', 0.0),
            'completed_qty': data.get('completed_qty', 0.0),
            'currency': data.get('currency', ''),
            'price': data.get('price', 0.0),
            'order_type': data.get('order_type', ''),
            'participation_rate': data.get('participation_rate', 0.0)
        }

    def write_to_sort_file(self, data: List[Dict], bin: str, filename: str = None) -> None:
        """Write data to CSV file with reordering - only for file storage"""
        try:
            if not self.tracking:
                return

            # For database storage, just use regular write_to_storage
            from source.config import app_config
            if getattr(app_config, 'use_database_storage', False):
                self.write_to_storage(data)
                return

            # For file storage, use the original sorting logic
            data_dir = self._get_user_data_dir()
            if not data_dir:
                return

            filepath = os.path.join(
                data_dir,
                filename if filename else f"{bin}.csv"
            )

            # Read existing entries if file exists
            existing_entries = []
            if os.path.exists(filepath):
                with open(filepath, 'r', newline='') as f:
                    reader = csv.DictReader(f)
                    existing_entries = list(reader)

            # Create a set of unique identifiers for existing entries
            existing_identifiers = {
                (entry['order_id'], entry['event_type'], entry['timestamp'])
                for entry in existing_entries
            }

            # Only add new entries that don't already exist
            new_entries = []
            for entry in data:
                identifier = (entry['order_id'], entry['event_type'], entry['timestamp'])
                if identifier not in existing_identifiers:
                    new_entries.append(entry)
                    existing_identifiers.add(identifier)

            # Combine non-duplicate entries
            all_entries = existing_entries + new_entries

            # Sort entries by timestamp and event_type
            all_entries.sort(key=lambda x: (
                x['timestamp'],
                0 if x['event_type'] == 'CANCELLED' else 1
            ))

            # Write all entries back to file
            with open(filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.headers)
                writer.writeheader()
                writer.writerows(all_entries)

        except Exception as e:
            self.logger.error(f"Error writing to file: {e}")
            raise

    def _get_user_data_dir(self):
        """Get user data directory - temporary method for file operations"""
        from source.config import app_config
        if getattr(app_config, 'use_file_storage', False):
            user_data_dir = os.path.join(app_config.data_directory, f"USER_{getattr(app_config, 'user_id', 'default')}", "orders")
            os.makedirs(user_data_dir, exist_ok=True)
            return user_data_dir
        return None

    def _write_order_to_file(self, data: Dict, event_type: str, cancel_timestamp: Optional[datetime] = None) -> None:
        """Write order event to file"""
        try:
            from source.orchestration.app_state.state_manager import app_state

            if not self.tracking:
                return

            # For database storage, use unified storage
            from source.config import app_config
            if getattr(app_config, 'use_database_storage', False):
                entry = self._prepare_order_entry(data, event_type, cancel_timestamp)
                self.write_to_storage([entry], timestamp=cancel_timestamp)
                return

            # For file storage, use the original sorting logic
            current_bin = app_state.get_current_bin()
            next_bin = app_state.get_next_bin()

            if cancel_timestamp and event_type == "CANCELLED":
                minute_bar_bin = cancel_timestamp.strftime('%H%M')
            else:
                minute_bar_bin = next_bin or current_bin or "0000"

            entry = self._prepare_order_entry(data, event_type, cancel_timestamp)
            self.write_to_sort_file([entry], minute_bar_bin)

            self.logger.info(f"📁 ORDER_FILE_WRITTEN: {event_type} -> {minute_bar_bin}.csv")

        except Exception as e:
            self.logger.error(f"❌ Error writing order to file: {e} - {data}")
            raise ValueError(f"Error writing order to file: {e} - {data}")

    def add_order(self, order_data: Dict) -> None:
        """Add a new order"""
        with self._lock:
            order = Order.from_dict(order_data)
            self._orders[order.order_id] = order

            self.logger.info(f"📝 ORDER_CREATED: {order.order_id}")
            self.logger.info(f"   Symbol: {order.symbol}")
            self.logger.info(f"   Side: {order.side}")
            self.logger.info(f"   Quantity: {order.original_qty}")

            if self.tracking:
                self._write_order_to_file(order.to_dict(), "NEW")

        self._notify_callbacks(self._orders.copy())

    def cancel_order(self, order_id: str, updates: Dict, cancel_timestamp: datetime) -> None:
        """Cancel an existing order"""
        with self._lock:
            if order_id in self._orders:
                order = self._orders[order_id]

                self.logger.info(f"🚫 ORDER_CANCEL_REQUESTED: {order_id}")

                order.cancelled = True
                order.cancel_timestamp = cancel_timestamp

                filtered_updates = {k: v for k, v in updates.items() if k != 'submit_timestamp'}

                for key, value in filtered_updates.items():
                    if hasattr(order, key):
                        setattr(order, key, value)

                if self.tracking:
                    self._write_order_to_file(order.to_dict(), "CANCELLED", cancel_timestamp)

                self.logger.info(f"✅ ORDER_CANCELLED: {order_id}")

        self._notify_callbacks(self._orders.copy())

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get a specific order"""
        with self._lock:
            return self._orders.get(order_id)

    def get_all_orders(self) -> Dict[str, Order]:
        """Get all current orders"""
        with self._lock:
            return self._orders.copy()

    def register_update_callback(self, callback: Callable[[Dict[str, Order]], None]) -> None:
        """Alias for register_callback to maintain compatibility"""
        self.register_callback(callback)