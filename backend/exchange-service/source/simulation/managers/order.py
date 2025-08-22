# source/simulation/managers/order.py

import csv
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass

from source.simulation.managers.utils import TrackingManager, CallbackManager
from source.simulation.core.enums.side import Side
from source.utils.timezone_utils import to_iso_string


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
        # Handle submit_timestamp
        submit_timestamp = data.get('submit_timestamp')
        if submit_timestamp is None:
            submit_timestamp = datetime.now()
        elif isinstance(submit_timestamp, str):
            submit_timestamp = datetime.fromisoformat(submit_timestamp)
        elif not isinstance(submit_timestamp, datetime):
            submit_timestamp = datetime.now()

        # Handle start_timestamp
        start_timestamp = data.get('start_timestamp', submit_timestamp)
        if start_timestamp is None:
            start_timestamp = submit_timestamp
        elif isinstance(start_timestamp, str):
            start_timestamp = datetime.fromisoformat(start_timestamp)
        elif not isinstance(start_timestamp, datetime):
            start_timestamp = submit_timestamp

        # Handle cancel_timestamp
        cancel_timestamp = data.get('cancel_timestamp')
        if cancel_timestamp and isinstance(cancel_timestamp, str):
            cancel_timestamp = datetime.fromisoformat(cancel_timestamp)
        else:
            cancel_timestamp = None

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
            submit_timestamp=submit_timestamp,
            start_timestamp=start_timestamp,
            cancelled=data.get('cancelled', False),
            cancel_timestamp=cancel_timestamp
        )


@dataclass
class OrderProgress:
    """Tracks order progress through market bins"""
    order_id: str
    cl_order_id: str
    symbol: str
    side: str
    original_qty: float
    remaining_qty: float
    completed_qty: float
    currency: str
    price: Optional[float]
    order_type: str
    participation_rate: float
    order_state: str  # 'WORKING', 'COMPLETED', 'CANCELLED'
    submit_timestamp: datetime
    start_timestamp: datetime  # Current market bin start or latest update
    last_update_timestamp: datetime
    market_bin: str  # Current market bin (HHMM format)
    tag: Optional[str] = None
    conviction_id: Optional[str] = None
    cancel_timestamp: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
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
            'order_state': self.order_state,
            'submit_timestamp': self.submit_timestamp.isoformat(),
            'start_timestamp': self.start_timestamp.isoformat(),
            'last_update_timestamp': self.last_update_timestamp.isoformat(),
            'market_bin': self.market_bin,
            'tag': self.tag,
            'conviction_id': self.conviction_id,
            'cancel_timestamp': self.cancel_timestamp.isoformat() if self.cancel_timestamp else None
        }


class OrderManager(TrackingManager, CallbackManager):
    def __init__(self, tracking: bool = False):
        headers = [
            'book_id', 'timestamp', 'order_id', 'cl_order_id', 'symbol', 'side',
            'original_qty', 'remaining_qty', 'completed_qty', 'currency', 'price',
            'order_type', 'participation_rate', 'order_state', 'submit_timestamp',
            'start_timestamp', 'market_bin', 'tag', 'conviction_id'
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
        self._order_progress: Dict[str, OrderProgress] = {}
        # Store current book_id context for database writes
        self._current_book_id: Optional[str] = None

    def set_book_context(self, book_id: str) -> None:
        """Set the current book context for this OrderManager instance"""
        self._current_book_id = book_id
        self.logger.debug(f"📋 OrderManager book context set to: {book_id}")

    def _get_current_book_id(self) -> str:
        """Override parent method to use stored book context"""
        if self._current_book_id:
            self.logger.debug(f"📍 Using OrderManager book context: {self._current_book_id}")
            return self._current_book_id

        # Fallback to parent implementation
        try:
            from source.orchestration.app_state.state_manager import app_state
            book_id = app_state.get_book_id()
            self.logger.debug(f"📍 Got book ID from app_state: {book_id}")
            if book_id:
                return book_id
        except Exception as e:
            self.logger.warning(f"⚠️ Error getting book ID from app_state: {e}")

        # Final fallback - raise error
        self.logger.error(f"❌ No book context available in OrderManager")
        raise ValueError("No book context available for database write")

    def initialize_orders(self, orders: Dict[str, Dict], timestamp: datetime) -> None:
        """Initialize orders from snapshot data with progress tracking"""
        with self._lock:
            try:
                from source.orchestration.app_state.state_manager import app_state
                current_bin = app_state.get_current_bin() or "0000"

                for order_id, order_data in orders.items():
                    order = Order.from_dict(order_data)
                    self._orders[order_id] = order

                    # Create progress tracking entry
                    progress = OrderProgress(
                        order_id=order.order_id,
                        cl_order_id=order.cl_order_id,
                        symbol=order.symbol,
                        side=order.side,
                        original_qty=order.original_qty,
                        remaining_qty=order.remaining_qty,
                        completed_qty=order.completed_qty,
                        currency=order.currency,
                        price=order.price,
                        order_type=order.order_type,
                        participation_rate=order.participation_rate,
                        order_state='WORKING' if not order.cancelled else 'CANCELLED',
                        submit_timestamp=order.submit_timestamp,
                        start_timestamp=timestamp,
                        last_update_timestamp=timestamp,
                        market_bin=current_bin,
                        conviction_id=order_data.get('conviction_id'),
                        tag=order_data.get('tag')
                    )

                    self._order_progress[order_id] = progress

                    # Track in database
                    if self.tracking:
                        self._save_order_progress(progress)

                self.logger.info(f"📋 Initialized {len(orders)} orders in OrderManager")

            except Exception as e:
                self.logger.error(f"❌ Error initializing orders: {e}")

    def _prepare_order_entry(self, order_data: Dict, event_type: str, timestamp: datetime) -> Dict:
        """Prepare order data for file storage with event type"""
        entry = {
            'timestamp': timestamp.isoformat(),
            'event_type': event_type,
            **order_data
        }
        return entry

    def write_to_file(self, data: List[Dict], filename: str) -> None:
        """Write order data to file with duplicate prevention"""
        try:
            filepath = os.path.join(self.output_dir, filename)

            # Read existing entries to prevent duplicates
            existing_entries = []
            existing_identifiers = set()

            if os.path.exists(filepath):
                with open(filepath, 'r', newline='') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        existing_entries.append(row)
                        # Create unique identifier from order_id, event_type, and timestamp
                        identifier = (row['order_id'], row['event_type'], row['timestamp'])
                        existing_identifiers.add(identifier)

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

    def _track_order_event(self, order: Order, event_type: str) -> None:
        """Track order event in database if tracking is enabled"""
        try:
            if not self.tracking:
                return

            # Get current timestamp
            current_time = datetime.now()

            # Create tracking record as DICTIONARY matching the headers
            tracking_data = {
                'book_id': self._get_current_book_id(),
                'timestamp': current_time,
                'order_id': order.order_id,
                'cl_order_id': order.cl_order_id,
                'symbol': order.symbol,
                'side': order.side,
                'original_qty': order.original_qty,
                'remaining_qty': order.remaining_qty,
                'completed_qty': order.completed_qty,
                'currency': order.currency,
                'price': order.price,
                'order_type': order.order_type,
                'participation_rate': order.participation_rate,
                'order_state': 'WORKING' if not order.cancelled else 'CANCELLED',
                'submit_timestamp': order.submit_timestamp,
                'start_timestamp': order.start_timestamp,
                'market_bin': "0000",  # Default bin
                'tag': None,
                'conviction_id': None
            }

            # Use write_to_storage with a LIST of DICTIONARIES
            self.write_to_storage([tracking_data], timestamp=current_time)

        except Exception as e:
            self.logger.warning(f"⚠️ Error tracking order event {event_type} for {order.order_id}: {e}")

    def add_order(self, order_data: Dict[str, Any]) -> bool:
        """Add order with enhanced validation and error handling"""
        try:
            # Validate required fields
            required_fields = ['order_id', 'cl_order_id', 'symbol', 'side', 'original_qty']
            for field in required_fields:
                if field not in order_data:
                    self.logger.error(f"❌ Missing required field '{field}' in order_data")
                    return False

            # Create order object
            order = Order.from_dict(order_data)

            # Validate order before storing
            if not order.order_id or not order.symbol:
                self.logger.error(f"❌ Invalid order data: order_id={order.order_id}, symbol={order.symbol}")
                return False

            with self._lock:
                # Store order
                self._orders[order.order_id] = order

                # Log order addition
                self.logger.info(f"✅ Order {order.order_id} added to OrderManager")
                self.logger.debug(
                    f"📊 Order details: symbol={order.symbol}, side={order.side}, qty={order.original_qty}")

                # Create progress tracking entry
                from source.orchestration.app_state.state_manager import app_state
                current_bin = app_state.get_current_bin() or "0000"
                current_time = datetime.now()

                progress = OrderProgress(
                    order_id=order.order_id,
                    cl_order_id=order.cl_order_id,
                    symbol=order.symbol,
                    side=order.side,
                    original_qty=order.original_qty,
                    remaining_qty=order.remaining_qty,
                    completed_qty=order.completed_qty,
                    currency=order.currency,
                    price=order.price,
                    order_type=order.order_type,
                    participation_rate=order.participation_rate,
                    order_state='WORKING',
                    submit_timestamp=order.submit_timestamp,
                    start_timestamp=current_time,
                    last_update_timestamp=current_time,
                    market_bin=current_bin,
                    conviction_id=order_data.get('conviction_id'),
                    tag=order_data.get('tag')
                )

                self._order_progress[order.order_id] = progress

                # Track in database if tracking enabled
                if self.tracking:
                    try:
                        self._save_order_progress(progress)
                    except Exception as e:
                        self.logger.warning(f"⚠️ Error tracking order event: {e}")

                # Submit to exchange (with proper error handling now)
                try:
                    self._submit_order_to_exchange(order)
                except Exception as e:
                    self.logger.error(f"❌ Failed to submit order {order.order_id} to exchange: {e}")
                    # Don't return False here - order is still added to OrderManager
                    # The exchange submission failure is logged but not blocking

                # Notify callbacks
                self._notify_callbacks(self._orders.copy())

                return True

        except Exception as e:
            self.logger.error(f"❌ Error adding order: {e}")
            return False

    def update_order_progress_for_market_bin(self, timestamp: datetime) -> None:
        """Update all order progress for current market bin"""
        with self._lock:
            try:
                from source.orchestration.app_state.state_manager import app_state
                current_bin = app_state.get_current_bin() or "0000"

                # Get trade information to calculate completion
                trade_manager = app_state.trade_manager

                updated_orders = []

                for order_id, order in self._orders.items():
                    # Get or create progress entry
                    if order_id not in self._order_progress:
                        self._order_progress[order_id] = OrderProgress(
                            order_id=order.order_id,
                            cl_order_id=order.cl_order_id,
                            symbol=order.symbol,
                            side=order.side,
                            original_qty=order.original_qty,
                            remaining_qty=order.remaining_qty,
                            completed_qty=order.completed_qty,
                            currency=order.currency,
                            price=order.price,
                            order_type=order.order_type,
                            participation_rate=order.participation_rate,
                            order_state='WORKING' if not order.cancelled else 'CANCELLED',
                            submit_timestamp=order.submit_timestamp,
                            start_timestamp=timestamp,
                            last_update_timestamp=timestamp,
                            market_bin=current_bin
                        )

                    progress = self._order_progress[order_id]

                    if progress.order_state == 'COMPLETED':
                        continue  # Skip already completed orders

                    # Calculate completed quantity from trades
                    completed_qty = 0.0
                    if trade_manager:
                        trades = trade_manager.get_trades_for_order(order_id)
                        completed_qty = sum(float(trade['quantity']) for trade in trades)

                    # Update progress
                    old_state = progress.order_state
                    remaining_qty = max(0.0, progress.original_qty - completed_qty)

                    # Determine new state
                    new_state = 'WORKING'
                    if completed_qty >= progress.original_qty:
                        new_state = 'COMPLETED'
                        remaining_qty = 0.0
                        completed_qty = progress.original_qty
                    elif order.cancelled:
                        new_state = 'CANCELLED'
                        progress.cancel_timestamp = timestamp

                    # Update progress object
                    progress.remaining_qty = remaining_qty
                    progress.completed_qty = completed_qty
                    progress.order_state = new_state
                    progress.market_bin = current_bin
                    progress.start_timestamp = timestamp  # Latest bin timestamp
                    progress.last_update_timestamp = timestamp

                    # Save updated progress
                    if self.tracking:
                        self._save_order_progress(progress)

                    updated_orders.append(order_id)

                    # Log state changes
                    if old_state != new_state:
                        self.logger.info(f"📋 Order {order_id} state changed: {old_state} → {new_state}")
                        self.logger.info(f"📋 Completed: {completed_qty}/{progress.original_qty}, "
                                         f"Remaining: {remaining_qty}")

                if updated_orders:
                    self.logger.info(f"📋 Updated progress for {len(updated_orders)} orders in bin {current_bin}")

                    # Notify callbacks with updated orders
                    self._notify_callbacks(self._orders.copy())

            except Exception as e:
                self.logger.error(f"❌ Error updating order progress for market bin: {e}")

    def _save_order_progress(self, progress: OrderProgress) -> None:
        """Save order progress to database"""
        try:
            if not self.tracking:
                return

            # Convert progress to tracking data format
            tracking_data = {
                'book_id': self._get_current_book_id(),
                'timestamp': progress.last_update_timestamp,
                'order_id': progress.order_id,
                'cl_order_id': progress.cl_order_id,
                'symbol': progress.symbol,
                'side': progress.side,
                'original_qty': progress.original_qty,
                'remaining_qty': progress.remaining_qty,
                'completed_qty': progress.completed_qty,
                'currency': progress.currency,
                'price': progress.price,
                'order_type': progress.order_type,
                'participation_rate': progress.participation_rate,
                'order_state': progress.order_state,
                'submit_timestamp': progress.submit_timestamp,
                'start_timestamp': progress.start_timestamp,
                'market_bin': progress.market_bin,
                'tag': progress.tag,
                'conviction_id': progress.conviction_id
            }

            self.write_to_storage([tracking_data], timestamp=progress.last_update_timestamp)

        except Exception as e:
            self.logger.warning(f"⚠️ Error saving order progress for {progress.order_id}: {e}")

    def cancel_order(self, order_id: str, updates: Dict, cancel_timestamp: datetime) -> None:
        """Cancel an existing order"""
        with self._lock:
            if order_id in self._orders:
                order = self._orders[order_id]

                self.logger.info(f"🚫 ORDER_CANCEL_REQUESTED: {order_id}")

                order.cancelled = True
                order.cancel_timestamp = cancel_timestamp

                # Update progress
                progress = self._order_progress.get(order_id)
                if progress:
                    progress.order_state = 'CANCELLED'
                    progress.cancel_timestamp = cancel_timestamp
                    progress.last_update_timestamp = cancel_timestamp

                    # Save updated progress
                    if self.tracking:
                        self._save_order_progress(progress)

                filtered_updates = {k: v for k, v in updates.items() if k != 'submit_timestamp'}

                for key, value in filtered_updates.items():
                    if hasattr(order, key):
                        setattr(order, key, value)

                if self.tracking:
                    entry = self._prepare_order_entry(order.to_dict(), "CANCELLED", cancel_timestamp)
                    self.write_to_storage([entry], timestamp=cancel_timestamp)

                self._cancel_order_from_exchange(order)

                self.logger.info(f"✅ ORDER_CANCELLED: {order_id}")

        self._notify_callbacks(self._orders.copy())

    def _cancel_order_from_exchange(self, order: Order) -> None:
        """Cancel order from exchange market"""
        try:
            from source.orchestration.app_state.state_manager import app_state

            # Check if exchange is available
            if not app_state.exchange:
                self.logger.error("❌ No exchange available for order cancellation")
                self.logger.error("❌ This indicates the exchange was not properly initialized")
                return

            # Validate exchange is properly initialized
            if not hasattr(app_state.exchange, 'get_market'):
                self.logger.error(f"❌ Exchange object {type(app_state.exchange)} does not have get_market method")
                return

            # Get market for the symbol
            try:
                market = app_state.exchange.get_market(order.symbol)
            except Exception as e:
                self.logger.error(f"❌ Error calling get_market for symbol {order.symbol}: {e}")
                return

            if not market:
                self.logger.error(f"❌ No market available for symbol: {order.symbol}")
                self.logger.error(
                    f"❌ Available markets: {getattr(app_state.exchange, '_markets', {}).keys() if hasattr(app_state.exchange, '_markets') else 'Unknown'}")
                return

            # Delete order from market
            try:
                market.delete_order(order.order_id, datetime.now())
                self.logger.info(f"✅ Order {order.order_id} deleted from exchange market")
            except Exception as e:
                self.logger.error(f"❌ Error deleting order from market: {e}")
                self.logger.error(f"❌ Market: {market}, Order: {order.order_id}")

        except Exception as e:
            self.logger.error(f"❌ Error deleting order {order.order_id} from exchange: {e}")
            self.logger.error(f"❌ This error occurred in OrderManager._cancel_order_from_exchange")

    def update_order(self, order_id: str, updates: Dict[str, Any], timestamp: datetime) -> bool:
        """Update an existing order with new state (e.g., after fills)"""
        try:
            with self._lock:
                if order_id not in self._orders:
                    self.logger.warning(f"⚠️ Cannot update order {order_id}: not found in memory")
                    return False

                order = self._orders[order_id]
                old_remaining = order.remaining_qty
                old_completed = order.completed_qty
                old_status = getattr(order, 'status', 'UNKNOWN')

                # Update order fields
                for field, value in updates.items():
                    if hasattr(order, field):
                        setattr(order, field, value)
                        self.logger.debug(f"📝 Updated order {order_id}.{field} = {value}")

                # Update progress tracking
                if order_id in self._order_progress:
                    progress = self._order_progress[order_id]
                    progress.remaining_qty = updates.get('remaining_qty', progress.remaining_qty)
                    progress.completed_qty = updates.get('completed_qty', progress.completed_qty)
                    progress.order_state = updates.get('status', progress.order_state)
                    progress.last_update_timestamp = timestamp

                    self.logger.info(f"✅ ORDER_UPDATE: {order_id}")
                    self.logger.info(f"   📊 Remaining: {old_remaining} → {progress.remaining_qty}")
                    self.logger.info(f"   📊 Completed: {old_completed} → {progress.completed_qty}")
                    self.logger.info(f"   📊 Status: {old_status} → {progress.order_state}")

                # Track the update event
                if self.tracking:
                    self._track_order_event(order, "FILL_UPDATE", timestamp)

                # Notify callbacks (so session service gets updated!)
                self._notify_callbacks(self._orders.copy())

                return True

        except Exception as e:
            self.logger.error(f"❌ Error updating order {order_id}: {e}")
            return False

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get a specific order"""
        with self._lock:
            return self._orders.get(order_id)

    def get_all_orders(self) -> Dict[str, Order]:
        """Get all current orders"""
        with self._lock:
            return self._orders.copy()

    def get_order_progress(self, order_id: str) -> Optional[OrderProgress]:
        """Get current progress for an order"""
        with self._lock:
            return self._order_progress.get(order_id)

    def get_all_order_progress(self) -> Dict[str, OrderProgress]:
        """Get progress for all orders"""
        with self._lock:
            return self._order_progress.copy()

    def get_orders_by_symbol(self, symbol: str) -> Dict[str, Order]:
        """Get all orders for a specific symbol"""
        with self._lock:
            return {
                order_id: order for order_id, order in self._orders.items()
                if order.symbol == symbol
            }

    def get_orders_by_cl_order_id(self, cl_order_id: str) -> Dict[str, Order]:
        """Get all orders with matching cl_order_id"""
        with self._lock:
            return {
                order_id: order for order_id, order in self._orders.items()
                if order.cl_order_id == cl_order_id
            }

    def cancel_orders_by_cl_order_id(self, cl_order_id: str) -> bool:
        """Cancel all orders with matching cl_order_id"""
        with self._lock:
            orders_to_cancel = self.get_orders_by_cl_order_id(cl_order_id)

            if not orders_to_cancel:
                self.logger.info(f"🔍 No orders found with cl_order_id: {cl_order_id}")
                return True

            cancel_timestamp = datetime.now()
            for order_id, order in orders_to_cancel.items():
                if not order.cancelled:
                    self.cancel_order(order_id, {}, cancel_timestamp)
                    self.logger.info(f"✅ Cancelled order {order_id} with cl_order_id {cl_order_id}")

            return True

    def get_active_orders(self) -> Dict[str, Order]:
        """Get all non-cancelled orders"""
        with self._lock:
            return {
                order_id: order for order_id, order in self._orders.items()
                if not order.cancelled
            }

    def get_orders_count(self) -> int:
        """Get total number of orders"""
        with self._lock:
            return len(self._orders)

    def clear_all_orders(self) -> None:
        """Clear all orders from memory"""
        with self._lock:
            self._orders.clear()
            self._order_progress.clear()
            self.logger.info("🧹 Cleared all orders from OrderManager")

        self._notify_callbacks(self._orders.copy())

    def register_update_callback(self, callback: Callable[[Dict[str, Order]], None]) -> None:
        """Alias for register_callback to maintain compatibility"""
        self.register_callback(callback)

    def get_order_statistics(self) -> Dict[str, Any]:
        """Get order statistics"""
        with self._lock:
            total_orders = len(self._orders)
            active_orders = len(self.get_active_orders())
            cancelled_orders = total_orders - active_orders

            symbols = set(order.symbol for order in self._orders.values())

            # Progress statistics
            completed_orders = len([p for p in self._order_progress.values() if p.order_state == 'COMPLETED'])
            working_orders = len([p for p in self._order_progress.values() if p.order_state == 'WORKING'])

            return {
                'total_orders': total_orders,
                'active_orders': active_orders,
                'cancelled_orders': cancelled_orders,
                'completed_orders': completed_orders,
                'working_orders': working_orders,
                'unique_symbols': len(symbols),
                'symbols': list(symbols)
            }

    def _submit_order_to_exchange(self, order: Order) -> None:
        """Submit order to exchange market for execution with proper error handling"""
        try:
            from source.orchestration.app_state.state_manager import app_state

            # Enhanced logging for debugging
            self.logger.info(
                f"EXCHANGE OBJECT IN ORDER MANAGER: {id(app_state.exchange) if app_state.exchange else 'None'}")

            # Check if exchange is available
            if not app_state.exchange:
                self.logger.error("❌ No exchange available for order submission")
                self.logger.error("❌ This indicates the exchange was not properly initialized in app_state")
                self.logger.error("❌ Check exchange initialization in book context setup")
                return

            # Validate exchange is properly initialized
            if not hasattr(app_state.exchange, 'get_market'):
                self.logger.error(f"❌ Exchange object {type(app_state.exchange)} does not have get_market method")
                return

            # Get market for the symbol
            try:
                market = app_state.exchange.get_market(order.symbol)
            except Exception as e:
                self.logger.error(f"❌ Error calling get_market for symbol {order.symbol}: {e}")
                return

            if not market:
                self.logger.error(f"❌ No market available for symbol: {order.symbol}")
                self.logger.error(
                    f"❌ Available markets: {getattr(app_state.exchange, '_markets', {}).keys() if hasattr(app_state.exchange, '_markets') else 'Unknown'}")
                return

            # Convert side string to enum
            try:
                side = Side.Buy if order.side.upper() == 'BUY' else Side.Sell
            except Exception as e:
                self.logger.error(f"❌ Error converting side '{order.side}' to enum: {e}")
                return

            # Submit order to market using add_order method (NOT submit_order)
            try:
                market.add_order(
                    submit_timestamp=order.submit_timestamp,
                    side=side,
                    qty=int(order.original_qty),
                    currency=order.currency,
                    price=0,  # Market order
                    cl_order_id=order.cl_order_id,
                    order_type=order.order_type,
                    participation_rate=order.participation_rate,
                    order_id=order.order_id,
                    skip_order_manager=True  # Prevent duplicate addition
                )
                self.logger.info(f"✅ Order {order.order_id} submitted to exchange")
            except Exception as e:
                self.logger.error(f"❌ Error submitting order to market: {e}")
                self.logger.error(f"❌ Market: {market}, Order: {order.order_id}")

        except Exception as e:
            self.logger.error(f"❌ Error submitting order {order.order_id} to exchange: {e}")
            self.logger.error(f"❌ This error occurred in OrderManager._submit_order_to_exchange")
