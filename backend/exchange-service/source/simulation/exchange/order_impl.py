from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from source.simulation.core.interfaces.order import Order_ABC
from source.simulation.core.enums.side import Side
from source.utils.timezone_utils import ensure_timezone_aware, to_iso_string, now_utc


@dataclass
class OrderData:
    participation_rate: float
    executed_value: Decimal = Decimal('0')
    executed_quantity: float = 0
    last_fill_timestamp: Optional[datetime] = None
    submit_timestamp: datetime = None
    start_timestamp: datetime = None

    def __post_init__(self):
        if self.submit_timestamp is None:
            raise ValueError("submit_time must be provided")

        # Ensure submit_timestamp is timezone-aware
        self.submit_timestamp = ensure_timezone_aware(self.submit_timestamp)

        # Set start time to submission time plus 5 seconds
        if self.start_timestamp is None:
            self.start_timestamp = self.submit_timestamp + timedelta(seconds=5)
        else:
            # Ensure start_timestamp is timezone-aware
            self.start_timestamp = ensure_timezone_aware(self.start_timestamp)


class Order(Order_ABC):
    def __init__(self,
                 submit_timestamp: datetime,
                 symbol: str,
                 order_id: str,
                 cl_order_id: str,
                 side: Side,
                 original_qty: float,
                 remaining_qty: float,
                 completed_qty: float,
                 currency: Optional[str],
                 price: Optional[Decimal],
                 participation_rate: float,
                 order_type: str = 'VWAP_A_ALGO'):

        self._symbol = symbol
        self._order_id = order_id
        self._cl_order_id = cl_order_id
        self._side = side
        self._original_qty = original_qty
        self._remaining_qty = remaining_qty
        self._completed_qty = completed_qty
        self._status = "WORKING"
        self._order_type = order_type
        self._currency = currency
        self._price = price

        # Ensure timezone-aware timestamps
        submit_timestamp = ensure_timezone_aware(submit_timestamp)

        self._vwap_data = OrderData(
            participation_rate=participation_rate,
            submit_timestamp=submit_timestamp,
        )
        self._submit_time = submit_timestamp
        self._last_fill_time = None

    # Required Order interface implementation
    def get_instrument(self) -> str:
        return self._symbol

    def get_order_id(self) -> str:
        return self._order_id

    def get_order_type(self) -> str:
        return self._order_type

    def get_order_fill_rate(self) -> str:
        return self._order_fill_rate

    def get_cl_ord_id(self) -> str:
        return self._cl_order_id

    def get_side(self) -> Side:
        return self._side

    def get_original_qty(self) -> float:
        return self._original_qty

    def get_remaining_qty(self) -> float:
        return self._remaining_qty

    def get_completed_qty(self) -> float:
        return self._completed_qty

    def set_original_qty(self, value: float) -> None:
        self._original_qty = value

    def set_remaining_qty(self, value: float) -> None:
        self._remaining_qty = value

    def set_completed_qty(self, value: float) -> None:
        self._completed_qty = value

    def get_currency(self) -> Optional[str]:
        return self._currency

    def get_price(self) -> Optional[Decimal]:
        return self._price

    def record_fill(self, quantity: float, price: Decimal, timestamp: Optional[datetime] = None) -> None:
        """Record a fill for this order using the provided timestamp"""
        # Ensure timezone-aware timestamp
        fill_timestamp = ensure_timezone_aware(timestamp) if timestamp else now_utc()

        self._vwap_data.executed_quantity += quantity
        self._vwap_data.executed_value += price * Decimal(str(quantity))
        self._vwap_data.last_fill_time = fill_timestamp
        self._remaining_qty -= quantity
        self._completed_qty = self._original_qty - self._remaining_qty
        self._status = 'WORKING' if self._remaining_qty > 0 else "COMPLETED"

    def cancel_order(self, timestamp: Optional[datetime] = None) -> None:
        """Cancel order with timezone-aware timestamp"""
        cancel_timestamp = ensure_timezone_aware(timestamp) if timestamp else now_utc()

        self._vwap_data.last_fill_time = cancel_timestamp
        self._remaining_qty = 0
        self._status = "CANCELLED"

    def get_vwap(self) -> Optional[Decimal]:
        """Get achieved VWAP price for this order"""
        if self._vwap_data.executed_quantity == 0:
            return None
        return self._vwap_data.executed_value / Decimal(str(self._vwap_data.executed_quantity))

    def get_participation_rate(self) -> float:
        """Get the target participation rate"""
        return self._vwap_data.participation_rate

    def get_submit_timestamp(self) -> datetime:
        """Get the original order submit time (timezone-aware)"""
        return self._vwap_data.submit_timestamp

    def get_start_timestamp(self) -> datetime:
        """Get the original order start time (timezone-aware)"""
        return self._vwap_data.start_timestamp

    def get_last_fill_timestamp(self) -> Optional[datetime]:
        """Get the timestamp of the last fill (timezone-aware)"""
        return self._vwap_data.last_fill_timestamp

    def can_execute(self, current_time: Optional[datetime] = None) -> bool:
        """Check if the order can execute based on timing"""
        if current_time is None:
            current_time = now_utc()
        else:
            current_time = ensure_timezone_aware(current_time)

        start_time = ensure_timezone_aware(self._vwap_data.start_timestamp)

        # Convert to same timezone for comparison
        if current_time.tzinfo != start_time.tzinfo:
            current_time = current_time.astimezone(start_time.tzinfo)

        return current_time >= start_time

    def get_execution_status(self) -> dict:
        """Get detailed execution status with timezone-aware timestamps"""
        return {
            'order_id': self._order_id,
            'cl_order_id': self._cl_order_id,
            'side': self._side.name,
            'original_qty': self._original_qty,
            'remaining_qty': self._remaining_qty,
            'completed_qty': self._completed_qty,
            'status': self._status,
            'executed_quantity': self._vwap_data.executed_quantity,
            'limit_currency': str(self._currency) if self._currency is not None else None,
            'limit_price': str(self._price) if self._price is not None else None,
            'participation_rate': self._vwap_data.participation_rate,
            'achieved_vwap': str(self.get_vwap()) if self.get_vwap() is not None else None,
            'submit_timestamp': to_iso_string(self._vwap_data.submit_timestamp),
            'start_timestamp': to_iso_string(self._vwap_data.start_timestamp),
            'last_fill_timestamp': to_iso_string(
                self._vwap_data.last_fill_timestamp) if self._vwap_data.last_fill_timestamp else to_iso_string(
                self._vwap_data.start_timestamp)
        }