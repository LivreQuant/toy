# source/exchange/impl/sim/execution.py
from decimal import Decimal
from datetime import datetime
import uuid
import time
from threading import RLock
from typing import Dict

from source.simulation.core.enums.side import Side, LS
from source.simulation.core.interfaces.market import Market_ABC
from source.simulation.exchange.account_impl import Account
from source.simulation.exchange.order_impl import Order
from source.exchange_logging.utils import get_exchange_logger
from source.exchange_logging.context import transaction_scope
from source.utils.timezone_utils import ensure_timezone_aware, to_iso_string


class ExecutionManager:
    """Manages order execution scheduling and processing"""

    def __init__(self, instrument: str, market: Market_ABC):
        self.instrument = instrument
        self._market = market
        self.logger = get_exchange_logger(f"{__name__}:{instrument}")
        self._lock = RLock()
        self.account = Account()
        self._pending_executions = {}

        # Execution statistics
        self._total_executions = 0
        self._total_cancellations = 0
        self._total_trade_volume = Decimal('0')
        self._execution_start_time = None

        self.logger.info(f"⚡ EXECUTION_MANAGER_INITIALIZED: {instrument}")
        self.logger.info("   Account manager created")
        self.logger.info("   Pending executions queue initialized")

    def schedule_cancellation(self, order: Order, timestamp: datetime) -> None:
        """Schedule an order for cancellation at a specific time"""
        # Ensure timezone-aware
        timestamp = ensure_timezone_aware(timestamp)

        with transaction_scope("schedule_cancellation", self.logger,
                               order_id=order.get_order_id(), instrument=self.instrument,
                               timestamp=to_iso_string(timestamp)) as txn_id:
            with self._lock:
                self.logger.info(f"🚫 SCHEDULING_CANCELLATION: {order.get_order_id()}")
                self.logger.info(f"   Instrument: {self.instrument}")
                self.logger.info(f"   Cancel Time: {timestamp}")
                self.logger.info(f"   Remaining Qty: {order.get_remaining_qty()}")
                self.logger.info(f"   Transaction ID: {txn_id}")

                if timestamp not in self._pending_executions:
                    self._pending_executions[timestamp] = []

                # Store the cancellation request
                self._pending_executions[timestamp].append(('CANCEL', order, timestamp))

                self.logger.log_business_event("CANCELLATION_SCHEDULED", {
                    "order_id": order.get_order_id(),
                    "cl_order_id": order.get_cl_ord_id(),
                    "instrument": self.instrument,
                    "cancel_timestamp": to_iso_string(timestamp),
                    "remaining_qty": order.get_remaining_qty(),
                    "transaction_id": txn_id
                })

                self.logger.info(f"✅ CANCELLATION_SCHEDULED: {order.get_order_id()}")

    def schedule_execution(self, order: Order, timestamp: datetime):
        """Schedule an order for execution at a specific time"""
        # Ensure timezone-aware
        timestamp = ensure_timezone_aware(timestamp)

        with transaction_scope("schedule_execution", self.logger,
                               order_id=order.get_order_id(), instrument=self.instrument,
                               timestamp=to_iso_string(timestamp)) as txn_id:
            with self._lock:
                self.logger.info(f"⚡ SCHEDULING_EXECUTION: {order.get_order_id()}")
                self.logger.info(f"   Instrument: {self.instrument}")
                self.logger.info(f"   Execution Time: {timestamp}")
                self.logger.info(f"   Remaining Qty: {order.get_remaining_qty()}")
                self.logger.info(f"   Participation Rate: {order.get_participation_rate()}")
                self.logger.info(f"   Transaction ID: {txn_id}")

                if timestamp not in self._pending_executions:
                    self._pending_executions[timestamp] = []

                self._pending_executions[timestamp].append(('FILL', order, timestamp))

                self.logger.log_business_event("EXECUTION_SCHEDULED", {
                    "order_id": order.get_order_id(),
                    "cl_order_id": order.get_cl_ord_id(),
                    "instrument": self.instrument,
                    "execution_timestamp": to_iso_string(timestamp),
                    "remaining_qty": order.get_remaining_qty(),
                    "participation_rate": order.get_participation_rate(),
                    "transaction_id": txn_id
                })

                self.logger.info(f"✅ EXECUTION_SCHEDULED: {order.get_order_id()}")

    def process_executions(self, prv_time: datetime, current_time: datetime, currency: str, price: Decimal):
        """Process all scheduled executions for the current time window"""

        # Ensure timezone-aware timestamps
        prv_time = ensure_timezone_aware(prv_time)
        current_time = ensure_timezone_aware(current_time)

        with transaction_scope("process_executions", self.logger,
                               instrument=self.instrument, prv_time=to_iso_string(prv_time),
                               current_time=to_iso_string(current_time), currency=currency,
                               price=str(price)) as master_txn_id:

            start_time = time.time()
            self._execution_start_time = datetime.now()

            with self._lock:
                self.logger.info("=" * 120)
                self.logger.info(f"⚡ EXECUTION_PROCESSING_START: {self.instrument}")
                self.logger.info("=" * 120)
                self.logger.info(f"⏰ Time Window: {prv_time} to {current_time}")
                self.logger.info(f"💰 Market Data: Price={price}, Currency={currency}")
                self.logger.info(f"📊 Pending Executions: {len(self._pending_executions)} time buckets")

                # Collect all relevant executions
                relevant_executions = []
                bucket_times = [prv_time, current_time]

                self.logger.info(f"🔍 SCANNING_PENDING_EXECUTIONS:")
                for exec_time, executions in self._pending_executions.items():
                    exec_time = ensure_timezone_aware(exec_time)
                    current_time_tz = ensure_timezone_aware(current_time)

                    # Convert to same timezone for comparison
                    if exec_time.tzinfo != current_time_tz.tzinfo:
                        exec_time = exec_time.astimezone(current_time_tz.tzinfo)

                    if exec_time <= current_time_tz:
                        self.logger.info(f"   Found {len(executions)} executions at {exec_time}")

                        for action, order, timestamp in executions:
                            timestamp = ensure_timezone_aware(timestamp)
                            prv_time_tz = ensure_timezone_aware(prv_time)

                            if action == "CANCEL":
                                self.logger.info(f"     CANCEL: {order.get_order_id()} at {timestamp}")
                                relevant_executions.append((timestamp, action, order))
                                bucket_times.append(max(prv_time_tz, timestamp))
                            else:  # FILL
                                order_start = ensure_timezone_aware(order.get_start_timestamp())
                                self.logger.info(f"     FILL: {order.get_order_id()} at {order_start}")
                                relevant_executions.append((order_start, action, order))
                                bucket_times.append(max(prv_time_tz, order_start))

                bucket_times = sorted(list(set(bucket_times)))
                self.logger.info(f"📅 PROCESSING_BUCKETS: {len(bucket_times) - 1} time buckets")
                self.logger.debug(f"   Bucket Times: {bucket_times}")

                # Process each bucket within the current minute bar
                execution_count = 0
                cancellation_count = 0
                total_fill_quantity = Decimal('0')
                trades_generated = []

                for i in range(len(bucket_times) - 1):
                    bucket_start = bucket_times[i]
                    bucket_end = bucket_times[i + 1]

                    current_minute = bucket_start.replace(second=0, microsecond=0)
                    bucket_volume = self._market.volume_tracker.get_current_minute_volume()

                    self.logger.info(f"🪣 PROCESSING_BUCKET [{i + 1}/{len(bucket_times) - 1}]:")
                    self.logger.info(f"   Time Range: {bucket_start} -> {bucket_end}")
                    self.logger.info(f"   Bucket Volume: {bucket_volume:,}")

                    # Get active orders in this bucket
                    bucket_orders = []
                    bucket_cancel_orders = []

                    for exec_time, action, order in relevant_executions:
                        exec_time = ensure_timezone_aware(exec_time)
                        bucket_end_tz = ensure_timezone_aware(bucket_end)

                        # Convert to same timezone for comparison
                        if exec_time.tzinfo != bucket_end_tz.tzinfo:
                            exec_time = exec_time.astimezone(bucket_end_tz.tzinfo)

                        if action == "FILL":
                            if exec_time < bucket_end_tz:
                                if order.get_remaining_qty() > 0:
                                    bucket_orders.append((order, exec_time))
                                    self.logger.debug(f"     Added FILL: {order.get_order_id()}")
                        elif action == "CANCEL":
                            if exec_time == bucket_end_tz:
                                bucket_cancel_orders.append(order.get_order_id())
                                self.logger.debug(f"     Added CANCEL: {order.get_order_id()}")

                    self.logger.info(
                        f"   Bucket Contents: {len(bucket_orders)} executions, {len(bucket_cancel_orders)} cancellations")

                    if len(bucket_orders) == 0:
                        # No orders to execute - just handle impact decay
                        self.logger.info("   🔄 PROCESSING_IMPACT_DECAY (no orders)")
                        self._execute_none(
                            start_timestamp=bucket_start,
                            end_timestamp=bucket_end,
                            currency=currency,
                            price=price,
                            bucket_volume=bucket_volume
                        )
                    else:
                        # Process orders
                        self.logger.info(f"   ⚡ PROCESSING_ORDER_EXECUTIONS:")
                        for j, (order, _) in enumerate(bucket_orders):
                            self.logger.info(f"     [{j + 1}/{len(bucket_orders)}] Processing {order.get_order_id()}")

                            volume_allocation = self._market.volume_tracker.get_available_volume(
                                bucket_start,
                                bucket_end
                            )

                            if order.get_remaining_qty() <= 0:
                                self.logger.warning(f"       ⚠️ SKIPPING: No remaining quantity")
                                self._execute_none(
                                    start_timestamp=bucket_start,
                                    end_timestamp=bucket_end,
                                    currency=currency,
                                    price=price,
                                    bucket_volume=bucket_volume
                                )
                                continue

                            if order.get_remaining_qty() > 0:
                                self.logger.info(f"       ⚡ EXECUTING_FILL: {order.get_order_id()}")
                                fill_result = self._execute_fill(
                                    order=order,
                                    timestamp=bucket_end,
                                    currency=currency,
                                    price=price,
                                    volume_allocation=volume_allocation,
                                    bucket_volume=bucket_volume,
                                    start_timestamp=bucket_start,
                                    end_timestamp=bucket_end,
                                )

                                if fill_result:
                                    execution_count += 1
                                    fill_qty, trade_ids = fill_result
                                    total_fill_quantity += fill_qty
                                    trades_generated.extend(trade_ids)

                                    self.logger.info(
                                        f"       ✅ FILL_EXECUTED: {fill_qty} shares, {len(trade_ids)} trades")

                            # Handle cancellations
                            if order.get_order_id() in bucket_cancel_orders:
                                self.logger.info(f"       🚫 EXECUTING_CANCELLATION: {order.get_order_id()}")
                                self._execute_cancel(order, bucket_end)
                                cancellation_count += 1
                                self.logger.info(f"       ✅ CANCELLATION_EXECUTED")

                # Update statistics
                self._total_executions += execution_count
                self._total_cancellations += cancellation_count
                self._total_trade_volume += total_fill_quantity

                # Log execution summary
                total_time = (time.time() - start_time) * 1000

                self.logger.info("=" * 120)
                self.logger.info(f"✅ EXECUTION_PROCESSING_COMPLETE: {self.instrument}")
                self.logger.info("=" * 120)
                self.logger.info(f"📊 EXECUTION_SUMMARY:")
                self.logger.info(f"   Executions Processed: {execution_count}")
                self.logger.info(f"   Cancellations Processed: {cancellation_count}")
                self.logger.info(f"   Total Fill Quantity: {total_fill_quantity}")
                self.logger.info(f"   Trades Generated: {len(trades_generated)}")
                self.logger.info(f"   Time Buckets Processed: {len(bucket_times) - 1}")
                self.logger.info(f"   Processing Time: {total_time:.2f}ms")
                self.logger.info(f"   Bucket Volume: {bucket_volume:,}")
                self.logger.info(f"   Market Price: ${price}")

                self.logger.info(f"📈 LIFETIME_STATISTICS:")
                self.logger.info(f"   Total Executions: {self._total_executions}")
                self.logger.info(f"   Total Cancellations: {self._total_cancellations}")
                self.logger.info(f"   Total Trade Volume: {self._total_trade_volume}")

                if trades_generated:
                    self.logger.info(f"🎯 TRADES_GENERATED:")
                    for trade_id in trades_generated[-5:]:  # Show last 5 trades
                        self.logger.info(f"     {trade_id}")

                self.logger.log_performance(
                    operation=f"process_executions[{self.instrument}]",
                    duration_ms=total_time,
                    additional_metrics={
                        "executions_processed": execution_count,
                        "cancellations_processed": cancellation_count,
                        "buckets_processed": len(bucket_times) - 1,
                        "bucket_volume": bucket_volume,
                        "price": str(price),
                        "total_fill_quantity": str(total_fill_quantity),
                        "trades_generated": len(trades_generated),
                        "master_transaction_id": master_txn_id
                    }
                )

                self.logger.info("=" * 120)

    def clear_pending_executions(self):
        """Clear completed executions and consolidate remaining active orders"""
        with self._lock:
            cleared_count = len(self._pending_executions)
            self._pending_executions = {}

            self.logger.info(f"🧹 CLEARED_PENDING_EXECUTIONS: {cleared_count} entries")
            self.logger.debug(f"   Execution manager ready for next market data")

    def _execute_none(self, start_timestamp: datetime, end_timestamp: datetime,
                      currency: str, price: Decimal, bucket_volume: int):
        """Handle impact decay when no fills occur"""

        # Ensure timezone-aware timestamps
        start_timestamp = ensure_timezone_aware(start_timestamp)
        end_timestamp = ensure_timezone_aware(end_timestamp)

        with transaction_scope("execute_none_impact_decay", self.logger,
                               instrument=self.instrument, price=str(price),
                               volume=bucket_volume) as txn_id:
            self.logger.info(f"🔄 IMPACT_DECAY_PROCESSING: {self.instrument}")
            self.logger.info(f"   Time Window: {start_timestamp} -> {end_timestamp}")
            self.logger.info(f"   No trades in this bucket")
            self.logger.info(f"   Market Price: ${price}")
            self.logger.info(f"   Bucket Volume: {bucket_volume:,}")

            impact_start_time = time.time()
            impacted_price = self._market.impact.calculate_price_impact(
                symbol=self.instrument,
                currency=currency,
                base_price=price,
                trade_volume=0,
                total_volume=bucket_volume,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                trade_id="0",
                is_buy=False
            )
            impact_duration = (time.time() - impact_start_time) * 1000

            self.logger.info(f"✅ IMPACT_DECAY_COMPLETE:")
            self.logger.info(f"   Base Price: ${price}")
            self.logger.info(f"   Impacted Price: ${impacted_price}")
            self.logger.info(f"   Duration: {impact_duration:.2f}ms")

            self.logger.log_performance(
                operation=f"impact_decay[{self.instrument}]",
                duration_ms=impact_duration,
                additional_metrics={
                    "base_price": str(price),
                    "impacted_price": str(impacted_price),
                    "bucket_volume": bucket_volume,
                    "transaction_id": txn_id
                }
            )

    def _execute_fill(self, order: Order, timestamp: datetime, currency: str,
                      price: Decimal, volume_allocation: int, bucket_volume: int,
                      start_timestamp: datetime, end_timestamp: datetime):

        # Ensure timezone-aware timestamps
        timestamp = ensure_timezone_aware(timestamp)
        start_timestamp = ensure_timezone_aware(start_timestamp)
        end_timestamp = ensure_timezone_aware(end_timestamp)

        with transaction_scope("execute_fill", self.logger,
                               order_id=order.get_order_id(), instrument=self.instrument,
                               volume_allocation=volume_allocation, price=str(price)) as txn_id:

            fill_start_time = time.time()

            try:
                from source.orchestration.app_state.state_manager import app_state
                if not app_state.portfolio_manager:
                    raise ValueError("No portfolio manager available")

                self.logger.info(f"⚡ FILL_EXECUTION_START: {order.get_order_id()}")
                self.logger.info(f"   Instrument: {self.instrument}")
                self.logger.info(
                    f"   Order Details: {order.get_side().name} {order.get_remaining_qty()}/{order.get_original_qty()}")
                self.logger.info(f"   Market Data: ${price}, Volume: {bucket_volume:,}")
                self.logger.info(f"   Volume Allocation: {volume_allocation:,}")
                self.logger.info(f"   Participation Rate: {order.get_participation_rate()}")

                # Get current position
                position_obj = app_state.portfolio_manager.get_position(self.instrument)
                current_position = position_obj.quantity if position_obj else Decimal('0')
                order_side = order.get_side()

                self.logger.info(f"📊 POSITION_ANALYSIS:")
                self.logger.info(f"   Current Position: {current_position}")
                self.logger.info(f"   Order Side: {order_side.name}")

                fill_qty = min(
                    int(volume_allocation * order.get_participation_rate()),
                    order.get_remaining_qty()
                )

                self.logger.log_calculation(
                    description="Fill quantity calculation",
                    inputs={
                        "volume_allocation": volume_allocation,
                        "participation_rate": order.get_participation_rate(),
                        "remaining_qty": order.get_remaining_qty(),
                        "current_position": str(current_position)
                    },
                    result=fill_qty,
                    details={
                        "order_id": order.get_order_id(),
                        "order_side": order_side.name,
                        "transaction_id": txn_id
                    }
                )

                if fill_qty <= 0:
                    self.logger.warning("⚠️ FILL_SKIPPED: Calculated quantity is zero")
                    return None

                fill_qty_decimal = Decimal(str(fill_qty))

                # Determine position state and risk logic
                long_short = LS.Long if current_position > 0 else (LS.Short if current_position < 0 else LS.Zero)

                self.logger.info(f"📈 RISK_ANALYSIS:")
                self.logger.info(f"   Position State: {long_short.name}")
                self.logger.info(f"   Fill Quantity: {fill_qty_decimal}")

                # Complex position logic with detailed logging
                risk_off_qty = Decimal('0')
                risk_on_qty = Decimal('0')

                if current_position != 0:
                    if (current_position > 0) and (order_side == Side.Sell):
                        is_flip_side = abs(fill_qty_decimal) > abs(current_position)
                        if is_flip_side:
                            # LONG + RISK OFF = CLOSE + SHORT (FLIP SIDE = TRUE)
                            risk_off_qty = abs(current_position)
                            risk_on_qty = abs(fill_qty_decimal) - abs(current_position)
                            self.logger.info(f"🔄 POSITION_FLIP: Long->Short")
                            self.logger.info(f"   Closing Long: {risk_off_qty}")
                            self.logger.info(f"   Opening Short: {risk_on_qty}")
                        else:
                            # LONG + RISK OFF
                            risk_off_qty = abs(fill_qty_decimal)
                            risk_on_qty = Decimal('0')
                            self.logger.info(f"📉 POSITION_REDUCE: Long position reduced by {risk_off_qty}")

                    elif (current_position < 0) and (order_side == Side.Buy):
                        is_flip_side = abs(fill_qty_decimal) > abs(current_position)
                        if is_flip_side:
                            # SHORT + RISK OFF = CLOSE + LONG (FLIP SIDE = TRUE)
                            risk_off_qty = abs(current_position)
                            risk_on_qty = abs(fill_qty_decimal) - abs(current_position)
                            self.logger.info(f"🔄 POSITION_FLIP: Short->Long")
                            self.logger.info(f"   Closing Short: {risk_off_qty}")
                            self.logger.info(f"   Opening Long: {risk_on_qty}")
                        else:
                            # SHORT + RISK OFF
                            risk_off_qty = abs(fill_qty_decimal)
                            risk_on_qty = Decimal('0')
                            self.logger.info(f"📈 POSITION_REDUCE: Short position reduced by {risk_off_qty}")
                    else:
                        # LONG + RISK ON (SHORT + RISK ON)
                        risk_off_qty = Decimal('0')
                        risk_on_qty = fill_qty_decimal
                        self.logger.info(f"📈 POSITION_INCREASE: {long_short.name} position increased by {risk_on_qty}")
                else:
                    # LONG + RISK ON (SHORT + RISK ON)
                    risk_off_qty = Decimal('0')
                    risk_on_qty = fill_qty_decimal
                    self.logger.info(f"🆕 POSITION_OPEN: New {order_side.name} position of {risk_on_qty}")

                # Log the risk breakdown
                self.logger.log_calculation(
                    description="Risk position breakdown",
                    inputs={
                        "total_fill_qty": str(fill_qty_decimal),
                        "current_position": str(current_position),
                        "order_side": order_side.name
                    },
                    result={
                        "risk_off_qty": str(risk_off_qty),
                        "risk_on_qty": str(risk_on_qty)
                    },
                    details={
                        "position_state": long_short.name,
                        "order_id": order.get_order_id(),
                        "transaction_id": txn_id
                    }
                )

                trades_generated = []

                # Execute risk-off portion first
                if risk_off_qty > Decimal('0'):
                    risk_off_trade_id = str(uuid.uuid4())
                    self.logger.info(f"🔴 EXECUTING_RISK_OFF: {risk_off_qty} shares [Trade ID: {risk_off_trade_id}]")

                    self._execute_single_fill(
                        order=order,
                        fill_qty=risk_off_qty,
                        is_risk_off=True,
                        initial_side=long_short,
                        timestamp=timestamp,
                        currency=currency,
                        price=price,
                        bucket_volume=bucket_volume,
                        start_timestamp=start_timestamp,
                        end_timestamp=end_timestamp,
                        trade_id=risk_off_trade_id
                    )
                    trades_generated.append(risk_off_trade_id)

                # Execute risk-on portion
                if risk_on_qty > Decimal('0'):
                    risk_on_trade_id = str(uuid.uuid4())
                    self.logger.info(f"🟢 EXECUTING_RISK_ON: {risk_on_qty} shares [Trade ID: {risk_on_trade_id}]")

                    self._execute_single_fill(
                        order=order,
                        fill_qty=risk_on_qty,
                        is_risk_off=False,
                        initial_side=long_short,
                        timestamp=timestamp,
                        currency=currency,
                        price=price,
                        bucket_volume=bucket_volume,
                        start_timestamp=start_timestamp,
                        end_timestamp=end_timestamp,
                        trade_id=risk_on_trade_id
                    )
                    trades_generated.append(risk_on_trade_id)

                fill_duration = (time.time() - fill_start_time) * 1000

                self.logger.info(f"✅ FILL_EXECUTION_COMPLETE: {order.get_order_id()}")
                self.logger.info(f"   Total Fill Quantity: {fill_qty_decimal}")
                self.logger.info(f"   Risk Off Quantity: {risk_off_qty}")
                self.logger.info(f"   Risk On Quantity: {risk_on_qty}")
                self.logger.info(f"   Trades Generated: {len(trades_generated)}")
                self.logger.info(f"   Execution Duration: {fill_duration:.2f}ms")

                return fill_qty_decimal, trades_generated

            except Exception as e:
                fill_duration = (time.time() - fill_start_time) * 1000
                self.logger.error(f"❌ FILL_EXECUTION_ERROR: {order.get_order_id()}")
                self.logger.error(f"   Duration: {fill_duration:.2f}ms")
                self.logger.error(f"   Error: {e}")
                raise ValueError(f"Error executing fill: {e}")

    def _execute_single_fill(self, order: Order, fill_qty: Decimal, is_risk_off: bool, initial_side: LS,
                             timestamp: datetime, currency: str, price: Decimal, bucket_volume: int,
                             start_timestamp: datetime, end_timestamp: datetime, trade_id: str):
        """Execute a single fill portion with comprehensive logging"""

        # Ensure timezone-aware timestamps
        timestamp = ensure_timezone_aware(timestamp)
        start_timestamp = ensure_timezone_aware(start_timestamp)
        end_timestamp = ensure_timezone_aware(end_timestamp)

        with transaction_scope("single_fill", self.logger,
                               trade_id=trade_id, fill_qty=str(fill_qty),
                               is_risk_off=is_risk_off, order_id=order.get_order_id()) as txn_id:

            fill_start_time = time.time()

            try:
                from source.orchestration.app_state.state_manager import app_state

                if not app_state.trade_manager:
                    raise ValueError("No trade manager available")

                self.logger.info(f"🎯 SINGLE_FILL_START: {trade_id}")
                self.logger.info(f"   Order ID: {order.get_order_id()}")
                self.logger.info(f"   Fill Quantity: {fill_qty}")
                self.logger.info(f"   Is Risk Off: {is_risk_off}")
                self.logger.info(f"   Initial Side: {initial_side.name}")
                self.logger.info(f"   Base Price: ${price}")
                self.logger.info(f"   Currency: {currency}")

                # Calculate commissions
                commissions = Decimal(str(round(fill_qty * Decimal('0.005'), 2)))

                self.logger.log_calculation(
                    description="Commission calculation",
                    inputs={
                        "fill_qty": str(fill_qty),
                        "commission_rate": "0.005"
                    },
                    result=str(commissions),
                    details={
                        "trade_id": trade_id,
                        "order_id": order.get_order_id()
                    }
                )

                # Calculate price with market impact
                impact_start_time = time.time()
                impacted_price = self._market.impact.calculate_price_impact(
                    symbol=self.instrument,
                    currency=currency,
                    base_price=price,
                    trade_volume=int(fill_qty),
                    total_volume=bucket_volume,
                    start_timestamp=start_timestamp,
                    end_timestamp=end_timestamp,
                    trade_id=trade_id,
                    is_buy=order.get_side() == Side.Buy
                )
                impact_duration = (time.time() - impact_start_time) * 1000

                # Calculate impact in basis points
                impact_bps = ((impacted_price / price) - 1) * 10000

                self.logger.info(f"💥 PRICE_IMPACT_CALCULATION:")
                self.logger.info(f"   Base Price: ${price}")
                self.logger.info(f"   Impacted Price: ${impacted_price}")
                self.logger.info(f"   Impact: {impact_bps:.2f} bps")
                self.logger.info(f"   Calculation Time: {impact_duration:.2f}ms")

                # Check account balance before fill
                balance_check_start = time.time()
                self.logger.info(f"🏦 ACCOUNT_BALANCE_CHECK: {trade_id}")

                self.account.check_balance_before_fill(
                    order=order,
                    start_timestamp=start_timestamp,
                    end_timestamp=end_timestamp,
                    impacted_price=impacted_price,
                    fill_qty=fill_qty,
                    commissions=commissions,
                    is_risk_off=is_risk_off,
                    initial_side=initial_side
                )
                balance_check_duration = (time.time() - balance_check_start) * 1000
                self.logger.info(f"✅ ACCOUNT_BALANCE_CHECK_COMPLETE: {balance_check_duration:.2f}ms")

                # Record the fill in the order
                order_fill_start = time.time()
                old_remaining = order.get_remaining_qty()
                old_completed = order.get_completed_qty()

                self.logger.info(f"📝 ORDER_FILL_RECORDING:")
                self.logger.info(f"   Before Fill: {old_remaining} remaining, {old_completed} completed")

                order.record_fill(int(fill_qty), impacted_price, timestamp)

                new_remaining = order.get_remaining_qty()
                new_completed = order.get_completed_qty()
                order_fill_duration = (time.time() - order_fill_start) * 1000

                self.logger.info(f"   After Fill: {new_remaining} remaining, {new_completed} completed")
                self.logger.info(f"   Fill Recording Duration: {order_fill_duration:.2f}ms")

                # Determine order status
                if new_remaining <= 0:
                    self.logger.info(f"🏁 ORDER_FULLY_FILLED: {order.get_order_id()}")
                    order_status = "COMPLETED"
                else:
                    self.logger.info(f"⏳ ORDER_PARTIALLY_FILLED: {order.get_order_id()} ({new_remaining} remaining)")
                    order_status = "PARTIAL"

                # Adjust balance after fill
                balance_adjust_start = time.time()
                self.logger.info(f"💰 ACCOUNT_BALANCE_ADJUSTMENT:")

                self.account.adjust_balance_after_fill(
                    order=order,
                    start_timestamp=start_timestamp,
                    end_timestamp=end_timestamp,
                    impacted_price=impacted_price,
                    fill_qty=fill_qty,
                    commissions=commissions,
                    is_risk_off=is_risk_off,
                    initial_side=initial_side,
                    trade_id=trade_id,
                    instrument=order.get_instrument()
                )
                balance_adjust_duration = (time.time() - balance_adjust_start) * 1000
                self.logger.info(f"✅ ACCOUNT_BALANCE_ADJUSTMENT_COMPLETE: {balance_adjust_duration:.2f}ms")

                # Log the complete trade execution
                self.logger.log_business_event("TRADE_EXECUTED", {
                    "trade_id": trade_id,
                    "order_id": order.get_order_id(),
                    "cl_order_id": order.get_cl_ord_id(),
                    "instrument": self.instrument,
                    "side": order.get_side().name,
                    "fill_qty": str(fill_qty),
                    "base_price": str(price),
                    "impacted_price": str(impacted_price),
                    "impact_bps": f"{impact_bps:.2f}",
                    "commissions": str(commissions),
                    "is_risk_off": is_risk_off,
                    "initial_side": initial_side.name,
                    "remaining_qty_after": str(new_remaining),
                    "order_status": order_status,
                    "currency": currency,
                    "start_timestamp": to_iso_string(start_timestamp),
                    "end_timestamp": to_iso_string(end_timestamp),
                    "transaction_id": txn_id
                })

                # Add to TradeManager with detailed data using correct bin timestamps
                trade_manager_start = time.time()
                self.logger.info(f"📊 TRADE_MANAGER_RECORDING:")

                # ✅ FIX: Calculate bin start from execution time (end_timestamp)
                from datetime import timedelta

                # The end_timestamp is the execution time (e.g., 19:33)
                # The bin start should be 1 minute earlier (e.g., 19:32)
                trade_end_timestamp = ensure_timezone_aware(end_timestamp)  # 19:33 (execution time)
                trade_start_timestamp = trade_end_timestamp - timedelta(minutes=1)  # 19:32 (bin start)

                self.logger.info(f"   Calculated trade bin timestamps:")
                self.logger.info(f"     Bin Start: {trade_start_timestamp}")
                self.logger.info(f"     Bin End (Execution): {trade_end_timestamp}")
                self.logger.info(f"   Original order start was: {start_timestamp}")

                trade_manager_data = {
                    'trade_id': trade_id,
                    'order_id': order.get_order_id(),
                    'cl_order_id': order.get_cl_ord_id(),
                    'symbol': self.instrument,
                    'side': "BUY" if order.get_side() == Side.Buy else "SELL",
                    'currency': order.get_currency(),
                    'price': str(impacted_price),
                    'quantity': str(fill_qty),
                    'detail': "VWAP1_RISK_OFF" if is_risk_off else "VWAP1_RISK_ON",
                    'start_timestamp': trade_start_timestamp,  # ✅ Calculated bin start (19:32)
                    'end_timestamp': trade_end_timestamp,  # ✅ Execution time (19:33)
                }
                app_state.trade_manager.add_trade(trade_manager_data)
                trade_manager_duration = (time.time() - trade_manager_start) * 1000

                self.logger.info(f"✅ TRADE_MANAGER_RECORDING_COMPLETE: {trade_manager_duration:.2f}ms")

                # Update portfolio position
                portfolio_start = time.time()
                self.logger.info(f"📈 PORTFOLIO_POSITION_UPDATE:")

                if app_state.portfolio_manager:
                    order_sign = Decimal('1') if order.get_side() == Side.Buy else Decimal('-1')

                    old_position = app_state.portfolio_manager.get_position(self.instrument)
                    old_qty = old_position.quantity if old_position else Decimal('0')
                    old_avg_price = old_position.avg_price if old_position else Decimal('0')

                    self.logger.info(f"   Before Update: {old_qty} @ ${old_avg_price}")

                    app_state.portfolio_manager.update_position(
                        symbol=self.instrument,
                        quantity=fill_qty * order_sign,
                        price=impacted_price,
                        currency=order.get_currency(),
                    )

                    new_position = app_state.portfolio_manager.get_position(self.instrument)
                    new_qty = new_position.quantity if new_position else Decimal('0')
                    new_avg_price = new_position.avg_price if new_position else Decimal('0')

                    self.logger.info(f"   After Update: {new_qty} @ ${new_avg_price}")

                    self.logger.log_state_change(
                        object_name=f"Position[{self.instrument}]",
                        old_state={
                            "quantity": str(old_qty),
                            "avg_price": str(old_avg_price)
                        },
                        new_state={
                            "quantity": str(new_qty),
                            "avg_price": str(new_avg_price)
                        },
                        change_reason=f"trade_execution[{trade_id}]"
                    )

                portfolio_duration = (time.time() - portfolio_start) * 1000
                self.logger.info(f"✅ PORTFOLIO_POSITION_UPDATE_COMPLETE: {portfolio_duration:.2f}ms")

                # Overall performance logging
                total_fill_time = (time.time() - fill_start_time) * 1000

                self.logger.info(f"🎯 SINGLE_FILL_SUMMARY: {trade_id}")
                self.logger.info(f"   Order ID: {order.get_order_id()}")
                self.logger.info(f"   Fill Quantity: {fill_qty}")
                self.logger.info(f"   Execution Price: ${impacted_price}")
                self.logger.info(f"   Price Impact: {impact_bps:.2f} bps")
                self.logger.info(f"   Commissions: ${commissions}")
                self.logger.info(f"   Order Status: {order_status}")
                self.logger.info(f"   Total Duration: {total_fill_time:.2f}ms")

                self.logger.log_performance(
                    operation=f"single_fill_execution[{trade_id}]",
                    duration_ms=total_fill_time,
                    additional_metrics={
                        "fill_qty": str(fill_qty),
                        "price_impact_bps": f"{impact_bps:.2f}",
                        "impact_calc_time_ms": f"{impact_duration:.2f}",
                        "balance_check_time_ms": f"{balance_check_duration:.2f}",
                        "balance_adjust_time_ms": f"{balance_adjust_duration:.2f}",
                        "order_fill_time_ms": f"{order_fill_duration:.2f}",
                        "trade_manager_time_ms": f"{trade_manager_duration:.2f}",
                        "portfolio_update_time_ms": f"{portfolio_duration:.2f}",
                        "is_risk_off": is_risk_off,
                        "order_id": order.get_order_id(),
                        "order_status": order_status
                    }
                )

                self.logger.info(f"✅ SINGLE_FILL_COMPLETE: {trade_id}")

            except Exception as e:
                fill_duration = (time.time() - fill_start_time) * 1000
                self.logger.error(f"❌ SINGLE_FILL_ERROR: {trade_id}")
                self.logger.error(f"   Order ID: {order.get_order_id()}")
                self.logger.error(f"   Duration: {fill_duration:.2f}ms")
                self.logger.error(f"   Error: {e}")
                self.logger.error(f"   Fill Qty: {fill_qty}")
                self.logger.error(f"   Is Risk Off: {is_risk_off}")
                raise ValueError(f"Error executing single fill: {e}")

    def _execute_cancel(self, order: Order, timestamp: datetime):
        """Execute order cancellation with detailed logging"""

        # Ensure timezone-aware timestamp
        timestamp = ensure_timezone_aware(timestamp)

        with transaction_scope("execute_cancel", self.logger,
                               order_id=order.get_order_id(), instrument=self.instrument) as txn_id:

            cancel_start_time = time.time()

            try:
                self.logger.info(f"🚫 CANCELLATION_EXECUTION_START: {order.get_order_id()}")
                self.logger.info(f"   Instrument: {self.instrument}")
                self.logger.info(f"   Cancel Time: {timestamp}")
                self.logger.info(f"   Transaction ID: {txn_id}")

                # Get state before cancellation
                old_remaining_qty = order.get_remaining_qty()
                old_completed_qty = order.get_completed_qty()
                old_status = order._status if hasattr(order, '_status') else "UNKNOWN"

                self.logger.info(f"📊 PRE_CANCELLATION_STATE:")
                self.logger.info(f"   Remaining Qty: {old_remaining_qty}")
                self.logger.info(f"   Completed Qty: {old_completed_qty}")
                self.logger.info(f"   Original Qty: {order.get_original_qty()}")
                self.logger.info(f"   Status: {old_status}")

                # Record cancellation in order
                order.cancel_order(timestamp)

                new_status = "CANCELLED"

                self.logger.log_state_change(
                    object_name=f"Order[{order.get_order_id()}]",
                    old_state={
                        "remaining_qty": str(old_remaining_qty),
                        "status": old_status
                    },
                    new_state={
                        "remaining_qty": "0",
                        "status": new_status
                    },
                    change_reason=f"order_cancellation[{txn_id}]"
                )

                self.logger.info(f"📝 ORDER_CANCELLATION_RECORDED:")
                self.logger.info(f"   Cancelled Quantity: {old_remaining_qty}")
                self.logger.info(f"   Executed Quantity: {old_completed_qty}")
                self.logger.info(f"   New Status: {new_status}")

                # Update order manager
                from source.orchestration.app_state.state_manager import app_state
                if app_state.order_manager:
                    order_manager_start = time.time()

                    order_data = {
                        'status': 'CANCELLED',
                        'leaves_qty': 0,
                    }
                    app_state.order_manager.cancel_order(order.get_order_id(), order_data, timestamp)

                    order_manager_duration = (time.time() - order_manager_start) * 1000
                    self.logger.info(f"📊 ORDER_MANAGER_UPDATE_COMPLETE: {order_manager_duration:.2f}ms")

                # Generate a unique trade ID for the cancellation record
                cancel_trade_id = str(uuid.uuid4())

                # Record cancellation in trade manager
                if app_state.trade_manager:
                    trade_manager_start = time.time()

                    trade_data = {
                        'trade_id': cancel_trade_id,
                        'order_id': order.get_order_id(),
                        'cl_order_id': order.get_cl_ord_id(),
                        'symbol': self.instrument,
                        'side': "BUY" if order.get_side() == Side.Buy else "SELL",
                        'currency': order.get_currency(),
                        'price': 0.0,
                        'quantity': 0,
                        'detail': "CANCELLED",
                        'start_timestamp': to_iso_string(timestamp),
                        'end_timestamp': to_iso_string(timestamp)
                    }
                    app_state.trade_manager.add_trade(trade_data)

                    trade_manager_duration = (time.time() - trade_manager_start) * 1000
                    self.logger.info(f"📊 TRADE_MANAGER_CANCELLATION_RECORD: {cancel_trade_id}")
                    self.logger.info(f"   Duration: {trade_manager_duration:.2f}ms")

                # Log business event
                self.logger.log_business_event("ORDER_CANCELLED", {
                    "order_id": order.get_order_id(),
                    "cl_order_id": order.get_cl_ord_id(),
                    "instrument": self.instrument,
                    "cancelled_qty": str(old_remaining_qty),
                    "completed_qty": str(old_completed_qty),
                    "original_qty": str(order.get_original_qty()),
                    "cancel_trade_id": cancel_trade_id,
                    "cancel_timestamp": to_iso_string(timestamp),
                    "transaction_id": txn_id
                })

                # Performance logging
                cancel_duration = (time.time() - cancel_start_time) * 1000

                self.logger.info(f"✅ CANCELLATION_EXECUTION_COMPLETE: {order.get_order_id()}")
                self.logger.info(f"   Cancelled Quantity: {old_remaining_qty}")
                self.logger.info(f"   Executed Quantity: {old_completed_qty}")
                self.logger.info(f"   Cancellation Trade ID: {cancel_trade_id}")
                self.logger.info(f"   Total Duration: {cancel_duration:.2f}ms")

                self.logger.log_performance(
                    operation=f"order_cancellation[{order.get_order_id()}]",
                    duration_ms=cancel_duration,
                    additional_metrics={
                        "cancelled_qty": str(old_remaining_qty),
                        "completed_qty": str(old_completed_qty),
                        "original_qty": str(order.get_original_qty()),
                        "cancel_trade_id": cancel_trade_id,
                        "instrument": self.instrument
                    }
                )

            except Exception as e:
                cancel_duration = (time.time() - cancel_start_time) * 1000
                self.logger.error(f"❌ CANCELLATION_EXECUTION_ERROR: {order.get_order_id()}")
                self.logger.error(f"   Duration: {cancel_duration:.2f}ms")
                self.logger.error(f"   Error: {e}")
                raise ValueError(f"Error executing cancel: {e}")

    def get_execution_statistics(self) -> Dict:
        """Get comprehensive execution statistics"""
        with self._lock:
            current_time = datetime.now()
            uptime = (
                        current_time - self._execution_start_time).total_seconds() if self._execution_start_time else 0

            stats = {
                'instrument': self.instrument,
                'total_executions': self._total_executions,
                'total_cancellations': self._total_cancellations,
                'total_trade_volume': str(self._total_trade_volume),
                'pending_executions_count': len(self._pending_executions),
                'pending_executions_times': [to_iso_string(ts) for ts in self._pending_executions.keys()],
                'uptime_seconds': uptime,
                'execution_start_time': to_iso_string(
                    self._execution_start_time) if self._execution_start_time else None,
                'executions_per_minute': (self._total_executions / (uptime / 60)) if uptime > 0 else 0
            }

            return stats

    def log_execution_summary(self) -> None:
        """Log comprehensive execution manager summary"""
        stats = self.get_execution_statistics()

        self.logger.info("=" * 100)
        self.logger.info(f"⚡ EXECUTION MANAGER SUMMARY: {self.instrument}")
        self.logger.info("=" * 100)
        self.logger.info(f"📊 LIFETIME STATISTICS:")
        self.logger.info(f"   Total Executions: {stats['total_executions']}")
        self.logger.info(f"   Total Cancellations: {stats['total_cancellations']}")
        self.logger.info(f"   Total Trade Volume: {stats['total_trade_volume']}")
        self.logger.info(f"   Uptime: {stats['uptime_seconds']:.1f} seconds")
        self.logger.info(f"   Executions/Minute: {stats['executions_per_minute']:.2f}")

        if stats['pending_executions_count'] > 0:
            self.logger.info(f"⏳ PENDING EXECUTIONS:")
            self.logger.info(f"   Count: {stats['pending_executions_count']}")
            for time_str in stats['pending_executions_times']:
                self.logger.info(f"   Scheduled: {time_str}")
        else:
            self.logger.info(f"✅ NO PENDING EXECUTIONS")

        self.logger.info("=" * 100)