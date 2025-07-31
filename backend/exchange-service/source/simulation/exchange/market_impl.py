from decimal import Decimal
from datetime import datetime
from typing import List, Optional, Dict
import uuid
import time
from threading import RLock

from source.simulation.core.enums.side import Side
from source.simulation.core.interfaces.order import Order_ABC
from source.simulation.core.interfaces.order_state import OrderState_ABC
from source.simulation.core.interfaces.market import Market_ABC
from source.simulation.exchange.order_impl import Order
from source.simulation.exchange.execution.execution import ExecutionManager
from source.simulation.exchange.execution.impact import ImpactState
from source.simulation.exchange.execution.volume import EnhancedVolumeTracker
from source.exchange_logging.utils import get_exchange_logger
from source.exchange_logging.context import transaction_scope
from source.utils.timezone_utils import ensure_timezone_aware, now_utc, to_iso_string, parse_iso_timestamp


class Market(Market_ABC):
    def __init__(self, instrument: str):
        self.instrument = instrument
        self.logger = get_exchange_logger(f"{__name__}:{instrument}")  # Include instrument in logger name

        # Core components
        self._lock = RLock()
        self._listener_lock = RLock()
        self._orders: Dict[str, Order_ABC] = {}

        # Helper components
        self.execution_manager = ExecutionManager(instrument, self)
        self.volume_tracker = EnhancedVolumeTracker()
        self.impact = ImpactState()

        # Track cancelled orders
        self._cancelled_orders: Dict[str, (Order_ABC, datetime)] = {}

        self.logger.info(f"Market initialized for instrument: {instrument}")

    def add_order(self, submit_timestamp: datetime, side: Side, qty: int, currency: Optional[str],
                  price: Optional[Decimal], cl_order_id: str, order_type: str,
                  participation_rate: float = 0.1, order_id: Optional[str] = None,
                  skip_order_manager: bool = False) -> str:
        """Add a new VWAP order to be processed on next market data update"""

        # Ensure timezone-aware timestamp
        submit_timestamp = ensure_timezone_aware(submit_timestamp)

        with transaction_scope("add_order", self.logger,
                               instrument=self.instrument, side=side.name, qty=qty,
                               cl_order_id=cl_order_id, order_type=order_type) as txn_id:

            with self._lock:
                # 🆕 ADD: Market order submission logging
                self.logger.info(f"🏛️ MARKET_ORDER_SUBMISSION: {self.instrument}")
                self.logger.info(f"   Client Order ID: {cl_order_id}")
                self.logger.info(f"   Side: {side.name}")
                self.logger.info(f"   Quantity: {qty}")
                self.logger.info(f"   Submit Time: {submit_timestamp}")
                self.logger.info(f"   Skip Order Manager: {skip_order_manager}")

                # Check existing orders
                existing_orders = [o for o in self._orders.values()
                                   if o.get_remaining_qty() > 0 and
                                   o.get_order_id() not in self._cancelled_orders]

                if existing_orders:
                    self.logger.warning(f"🚫 ORDER_REJECTED - symbol {self.instrument} already has active orders: "
                                        f"{[o.get_order_id() for o in existing_orders]}")
                    raise ValueError(
                        f"Symbol {self.instrument} already has an active order. Cancel existing order before submitting new one.")

                # Generate order ID
                final_order_id = order_id if order_id is not None else str(uuid.uuid4())

                self.logger.info(f"🆔 GENERATED_ORDER_ID: {final_order_id}")

                # Create order with timezone-aware timestamp
                order = Order(
                    submit_timestamp=submit_timestamp,
                    symbol=self.instrument,
                    order_id=final_order_id,
                    cl_order_id=cl_order_id,
                    side=side,
                    original_qty=qty,
                    remaining_qty=qty,
                    completed_qty=0,
                    currency=currency,
                    price=price,
                    order_type=order_type,
                    participation_rate=participation_rate,
                )

                # Store the order
                self._orders[final_order_id] = order

                self.logger.info(f"✅ MARKET_ORDER_STORED: {final_order_id}")

                self.logger.log_business_event("ORDER_CREATED", {
                    "order_id": final_order_id,
                    "cl_order_id": cl_order_id,
                    "instrument": self.instrument,
                    "side": side.name,
                    "original_qty": qty,
                    "remaining_qty": qty,
                    "completed_qty": 0,
                    "currency": currency,
                    "price": str(price) if price else "None",
                    "order_type": order_type,
                    "participation_rate": participation_rate,
                    "submit_timestamp": to_iso_string(submit_timestamp),
                    "transaction_id": txn_id
                })

                # Log order execution status
                execution_status = order.get_execution_status()
                self.logger.debug(f"Order execution status: {execution_status}")

                # ✅ MODIFIED: Only add to OrderManager if not skipping
                if not skip_order_manager:
                    # Add to OrderManager
                    from source.orchestration.app_state.state_manager import app_state
                    if app_state.order_manager:
                        order_data = {
                            'order_id': final_order_id,
                            'cl_order_id': cl_order_id,
                            'symbol': self.instrument,
                            'side': "BUY" if side == Side.Buy else "SELL",
                            'original_qty': qty,
                            'remaining_qty': qty,
                            'completed_qty': 0,
                            'currency': currency,
                            'price': float(price) if price else 0.0,
                            'leaves_qty': qty,
                            'cum_qty': 0,
                            'status': 'NEW',
                            'order_type': order_type,
                            'participation_rate': participation_rate,
                            'submit_timestamp': submit_timestamp,
                            'start_timestamp': order.get_start_timestamp(),
                        }
                        app_state.order_manager.add_order(order_data)
                        self.logger.debug(f"Order {final_order_id} added to OrderManager")
                else:
                    self.logger.info(f"⏭️ SKIPPED OrderManager - order {final_order_id} for initialization")

                return final_order_id

    def delete_order(self, order_id: str, submit_timestamp: datetime) -> OrderState_ABC:
        """Schedule an order for cancellation"""

        # Ensure timezone-aware timestamp
        submit_timestamp = ensure_timezone_aware(submit_timestamp)

        with transaction_scope("delete_order", self.logger,
                               order_id=order_id, instrument=self.instrument) as txn_id:

            with self._lock:
                order = self._orders.get(order_id)
                if order is None:
                    error_msg = f"Order {order_id} not found"
                    self.logger.error(error_msg)
                    raise ValueError(error_msg)

                # Check if order has already been cancelled
                if order_id in self._cancelled_orders:
                    error_msg = f"Order {order_id} has already been cancelled"
                    self.logger.warning(error_msg)
                    raise ValueError(error_msg)

                # Check if order has any remaining qty
                if order.get_remaining_qty() <= 0:
                    error_msg = f"Order {order_id} has no remaining quantity to cancel"
                    self.logger.warning(error_msg)
                    raise ValueError(error_msg)

                # Mark order as cancelled, do not cancel until the bucket is evaluated
                self._cancelled_orders[order_id] = (order, submit_timestamp)

                self.logger.log_business_event("ORDER_CANCEL_REQUESTED", {
                    "order_id": order_id,
                    "cl_order_id": order.get_cl_ord_id(),
                    "instrument": self.instrument,
                    "remaining_qty": order.get_remaining_qty(),
                    "cancel_request_timestamp": to_iso_string(submit_timestamp),
                    "transaction_id": txn_id
                })

                # Return current order state - actual cancellation happens during execution
                return order

    def update_market_state(self, market_data: dict) -> None:
        """Update market state and process orders"""

        with transaction_scope("market_data_update", self.logger,
                               instrument=self.instrument, price=market_data.get('price'),
                               volume=market_data.get('volume')) as txn_id:

            update_start_time = time.time()

            with self._lock:
                try:
                    from source.orchestration.app_state.state_manager import app_state

                    # Get timezone-aware timestamps
                    start_bin_timestamp = ensure_timezone_aware(app_state.get_current_timestamp())
                    stop_bin_timestamp = ensure_timezone_aware(app_state.get_next_timestamp())

                    currency = str(market_data['currency'])
                    price = Decimal(str(market_data['price']))
                    volume = int(market_data['volume'])

                    self.logger.log_data_flow(
                        source="MarketDataService",
                        destination=f"Market[{self.instrument}]",
                        data_type="MarketData",
                        data_summary=f"Price={price}, Volume={volume}, Currency={currency}"
                    )

                    # Update volume tracking with timezone-aware timestamp
                    volume_update_start = time.time()
                    old_volume = self.volume_tracker.current_bin_volume
                    self.volume_tracker.update_volume(stop_bin_timestamp, volume)
                    volume_update_duration = (time.time() - volume_update_start) * 1000

                    self.logger.debug(f"Volume updated: {old_volume} -> {volume} in {volume_update_duration:.2f}ms")

                    # ✅ ADD ORDER DEBUG LOGGING HERE
                    self.logger.info(f"🔍 Order Debug - Total orders in market: {len(self._orders)}")
                    for order_id, order in self._orders.items():
                        order_start = ensure_timezone_aware(order.get_start_timestamp())
                        stop_timestamp = ensure_timezone_aware(stop_bin_timestamp)

                        # Convert to same timezone for comparison
                        if order_start.tzinfo != stop_timestamp.tzinfo:
                            order_start = order_start.astimezone(stop_timestamp.tzinfo)

                        self.logger.info(f"  Order {order_id}: remaining={order.get_remaining_qty()}, "
                                         f"start_time={order_start}, "
                                         f"current_time={stop_timestamp}, "
                                         f"start <= current: {order_start <= stop_timestamp}, "
                                         f"cancelled={order_id in self._cancelled_orders}")

                    # Get active orders with timezone-aware comparison
                    active_orders = []
                    for order in self._orders.values():
                        if (order.get_remaining_qty() > 0 and
                                order.get_order_id() not in self._cancelled_orders):

                            # Ensure both timestamps are timezone-aware for comparison
                            order_start = ensure_timezone_aware(order.get_start_timestamp())
                            stop_timestamp = ensure_timezone_aware(stop_bin_timestamp)

                            # Convert to same timezone if needed
                            if order_start.tzinfo != stop_timestamp.tzinfo:
                                order_start = order_start.astimezone(stop_timestamp.tzinfo)

                            if order_start <= stop_timestamp:
                                active_orders.append(order)

                    self.logger.info(f"Processing {len(active_orders)} active orders")

                    for order in active_orders:
                        self.logger.debug(f"Active order: {order.get_order_id()} - "
                                          f"remaining: {order.get_remaining_qty()}, "
                                          f"start: {order.get_start_timestamp()}")

                    # Process cancellations
                    cancel_orders = self.get_cancel_orders()
                    if cancel_orders:
                        self.logger.info(f"Processing {len(cancel_orders)} cancellation requests")

                    cancellation_schedule_start = time.time()
                    for order, submit_timestamp in cancel_orders:
                        if order.get_remaining_qty() > 0:
                            self.execution_manager.schedule_cancellation(order, submit_timestamp)
                            self.logger.debug(f"Scheduled cancellation for order {order.get_order_id()}")
                    cancellation_schedule_duration = (time.time() - cancellation_schedule_start) * 1000

                    # Schedule executions for orders
                    execution_schedule_start = time.time()
                    for order in active_orders:
                        participation_qty = min(
                            order.get_remaining_qty(),
                            int(volume * order.get_participation_rate())
                        )

                        if participation_qty > 0:
                            order_start = ensure_timezone_aware(order.get_start_timestamp())
                            start_bin = ensure_timezone_aware(start_bin_timestamp)

                            # Convert to same timezone for comparison
                            if order_start.tzinfo != start_bin.tzinfo:
                                order_start = order_start.astimezone(start_bin.tzinfo)

                            if order_start < start_bin:
                                exec_time = start_bin_timestamp
                            else:
                                exec_time = order.get_start_timestamp()

                            self.execution_manager.schedule_execution(order, exec_time)

                            self.logger.debug(f"Scheduled execution for order {order.get_order_id()}: "
                                              f"{participation_qty} shares at {exec_time}")
                        else:
                            self.logger.debug(f"No execution scheduled for order {order.get_order_id()}: "
                                              f"participation_qty={participation_qty}")
                    execution_schedule_duration = (time.time() - execution_schedule_start) * 1000

                    # Process executions
                    execution_process_start = time.time()
                    self.execution_manager.process_executions(
                        prv_time=start_bin_timestamp,
                        current_time=stop_bin_timestamp,
                        currency=currency,
                        price=price
                    )
                    execution_process_duration = (time.time() - execution_process_start) * 1000

                    # Clear pending executions
                    clear_start = time.time()
                    self.execution_manager.clear_pending_executions()
                    clear_duration = (time.time() - clear_start) * 1000

                    # Overall performance logging
                    total_update_time = (time.time() - update_start_time) * 1000

                    self.logger.log_performance(
                        operation=f"market_state_update[{self.instrument}]",
                        duration_ms=total_update_time,
                        additional_metrics={
                            "active_orders": len(active_orders),
                            "cancel_orders": len(cancel_orders),
                            "volume": volume,
                            "price": str(price),
                            "volume_update_ms": f"{volume_update_duration:.2f}",
                            "cancellation_schedule_ms": f"{cancellation_schedule_duration:.2f}",
                            "execution_schedule_ms": f"{execution_schedule_duration:.2f}",
                            "execution_process_ms": f"{execution_process_duration:.2f}",
                            "clear_pending_ms": f"{clear_duration:.2f}",
                            "transaction_id": txn_id
                        }
                    )

                    # Log significant market movements
                    if hasattr(self, '_last_price'):
                        price_change_pct = ((price / self._last_price) - 1) * 100
                        if abs(price_change_pct) > 0.5:  # More than 0.5% change
                            self.logger.log_business_event("SIGNIFICANT_PRICE_MOVEMENT", {
                                "instrument": self.instrument,
                                "old_price": str(self._last_price),
                                "new_price": str(price),
                                "change_pct": f"{price_change_pct:.2f}%",
                                "volume": volume,
                                "transaction_id": txn_id
                            })

                    self._last_price = price

                except Exception as e:
                    update_duration = (time.time() - update_start_time) * 1000
                    self.logger.error(
                        f"Error updating market state for {self.instrument} after {update_duration:.2f}ms: {e}")
                    raise ValueError(f"Error updating market state: {e}")

    def get_instrument(self) -> str:
        return self.instrument

    def get_order(self, order_id: str) -> Optional[Order_ABC]:
        with self._lock:
            order = self._orders.get(order_id)
            if order:
                self.logger.debug(f"Retrieved order {order_id}: remaining_qty={order.get_remaining_qty()}")
            else:
                self.logger.debug(f"Order {order_id} not found")
            return order

    def get_buy_orders(self) -> List[Order_ABC]:
        with self._lock:
            buy_orders = [o for o in self._orders.values() if o.get_side() == Side.Buy]
            self.logger.debug(f"Retrieved {len(buy_orders)} buy orders")
            return buy_orders

    def get_sell_orders(self) -> List[Order_ABC]:
        with self._lock:
            sell_orders = [o for o in self._orders.values() if o.get_side() == Side.Sell]
            self.logger.debug(f"Retrieved {len(sell_orders)} sell orders")
            return sell_orders

    def get_cancel_orders(self) -> List:
        with self._lock:
            cancel_orders = [o for o in self._cancelled_orders.values()]
            self.logger.debug(f"Retrieved {len(cancel_orders)} pending cancellation orders")
            return cancel_orders

    def parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse timestamp string to timezone-aware datetime object"""
        try:
            result = parse_iso_timestamp(timestamp_str)
            self.logger.debug(f"Parsed timestamp '{timestamp_str}' -> {result}")
            return result
        except Exception as e:
            self.logger.error(f"Error parsing timestamp {timestamp_str}: {e}")
            raise ValueError(f"Error parsing timestamp {timestamp_str}: {e}")

    def get_pending_quantity(self) -> float:
        """Get total pending quantity for this market's orders"""
        with self._lock:
            pending_qty = 0
            active_order_count = 0

            for order in self._orders.values():
                if order.get_remaining_qty() > 0 and order.get_order_id() not in self._cancelled_orders:
                    active_order_count += 1
                    if order.get_side() == Side.Buy:
                        pending_qty += order.get_remaining_qty()
                    else:  # Side.Sell
                        pending_qty -= order.get_remaining_qty()

            self.logger.debug(f"Calculated pending quantity: {pending_qty} from {active_order_count} active orders")
            return pending_qty

    def get_market_summary(self) -> dict:
        """Get comprehensive market summary for logging/debugging"""
        with self._lock:
            total_orders = len(self._orders)
            active_orders = len([o for o in self._orders.values()
                                 if o.get_remaining_qty() > 0 and o.get_order_id() not in self._cancelled_orders])
            cancelled_orders = len(self._cancelled_orders)
            pending_qty = self.get_pending_quantity()

            summary = {
                "instrument": self.instrument,
                "total_orders": total_orders,
                "active_orders": active_orders,
                "cancelled_orders": cancelled_orders,
                "pending_quantity": pending_qty,
                "current_volume": self.volume_tracker.get_current_minute_volume(),
                "total_volume": self.volume_tracker.get_total_volume(),
                "last_price": str(getattr(self, '_last_price', 'N/A'))
            }

            return summary

    def log_market_summary(self):
        """Log a comprehensive market summary"""
        summary = self.get_market_summary()

        self.logger.info(f"=== Market Summary for {self.instrument} ===")
        for key, value in summary.items():
            if key != "instrument":
                self.logger.info(f"{key}: {value}")

        # Log recent orders
        with self._lock:
            if self._orders:
                self.logger.info("Recent orders:")
                # Show last 5 orders
                recent_orders = sorted(self._orders.values(),
                                       key=lambda x: x.get_submit_timestamp() if hasattr(x,
                                                                                         'get_submit_timestamp') else now_utc())[
                                -5:]
                for order in recent_orders:
                    status = "CANCELLED" if order.get_order_id() in self._cancelled_orders else "ACTIVE"
                    self.logger.info(
                        f"  {order.get_order_id()}: {order.get_side().name} {order.get_remaining_qty()}/{order.get_original_qty()} - {status}"
                    )