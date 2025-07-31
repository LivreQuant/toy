# source/simulation/managers/cash_flow.py
from enum import Enum
from typing import Dict, Optional, List, Any
from datetime import datetime
from dataclasses import dataclass
from decimal import Decimal
import uuid
from source.simulation.managers.utils import TrackingManager


class CashFlowType(Enum):
    ACCOUNT_TRANSFER = "ACCOUNT_TRANSFER"
    ACCOUNT_FEE = "ACCOUNT_FEE"
    PORTFOLIO_TRANSFER = "PORTFOLIO_TRANSFER"
    PORTFOLIO_FEE = "PORTFOLIO_FEE"
    EXTERNAL = "EXTERNAL"


@dataclass
class CashFlow:
    timestamp: str
    flow_type: CashFlowType
    from_account: str
    from_currency: str
    from_fx: Decimal
    from_amount: Decimal
    to_account: str
    to_currency: str
    to_fx: Decimal
    to_amount: Decimal
    instrument: Optional[str] = None
    trade_id: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self) -> Dict:
        from source.utils.timezone_utils import to_iso_string

        return {
            'timestamp': to_iso_string(self.timestamp) if isinstance(self.timestamp, datetime) else self.timestamp,
            'flow_type': self.flow_type.value,
            'from_account': self.from_account,
            'from_currency': self.from_currency,
            'from_fx': str(self.from_fx),
            'from_amount': str(self.from_amount),
            'to_account': self.to_account,
            'to_currency': self.to_currency,
            'to_fx': str(self.to_fx),
            'to_amount': str(self.to_amount),
            'instrument': self.instrument,
            'trade_id': self.trade_id,
            'description': self.description
        }


class CashFlowManager(TrackingManager):
    """Manages and tracks all cash flows between accounts and portfolio"""

    def __init__(self, tracking: bool = False):
        headers = [
            'timestamp', 'flow_type',
            'from_account', 'from_currency', 'from_fx', 'from_amount',
            'to_account', 'to_currency', 'to_fx', 'to_amount',
            'instrument', 'trade_id', 'description'
        ]

        super().__init__(
            manager_name="CashFlowManager",
            table_name="cash_flow_data",
            headers=headers,
            tracking=tracking
        )

        self.flows: List[CashFlow] = []
        self.historical_flows: List[CashFlow] = []

    def clear_current_flows(self) -> None:
        """Clear flows for the current iteration"""
        with self._lock:
            self.historical_flows.extend(self.flows)
            self.flows.clear()

    def record_flow(self, cash_flow: CashFlow) -> None:
        """Record a single cash flow"""
        with self._lock:
            self.flows.append(cash_flow)
            if self.tracking:
                data = [cash_flow.to_dict()]
                self.write_to_storage(data)

    def record_account_transfer(self,
                                from_account: str, from_currency: str, from_fx: Decimal, from_amount: Decimal,
                                to_account: str, to_currency: str, to_fx: Decimal, to_amount: Decimal,
                                timestamp: datetime,
                                trade_id: Optional[str] = None, instrument: Optional[str] = None,
                                description: Optional[str] = None) -> str:
        """Record transfers between internal accounts"""
        transfer_id = str(uuid.uuid4())

        cash_flow = CashFlow(
            timestamp=timestamp.isoformat(),
            flow_type=CashFlowType.ACCOUNT_TRANSFER,
            from_account=from_account,
            from_currency=from_currency,
            from_fx=from_fx,
            from_amount=from_amount,
            to_account=to_account,
            to_currency=to_currency,
            to_fx=to_fx,
            to_amount=to_amount,
            instrument=instrument,
            trade_id=trade_id,
            description=description
        )
        self.record_flow(cash_flow)
        return transfer_id

    def record_portfolio_transfer(self, account_type: str, is_inflow: bool,
                                  from_currency: str, from_fx: Decimal, from_amount: Decimal,
                                  to_currency: str, to_fx: Decimal, to_amount: Decimal,
                                  timestamp: datetime,
                                  trade_id: Optional[str] = None, instrument: Optional[str] = None,
                                  description: Optional[str] = None) -> None:
        """Record trade-related cash flows"""

        # Use current market timestamp
        from source.utils.timezone_utils import ensure_utc
        cash_flow_timestamp = ensure_utc(timestamp)

        from_account = "PORTFOLIO" if is_inflow else account_type
        to_account = account_type if is_inflow else "PORTFOLIO"

        cash_flow = CashFlow(
            timestamp=cash_flow_timestamp.isoformat(),
            flow_type=CashFlowType.PORTFOLIO_TRANSFER,
            from_account=from_account,
            from_currency=from_currency,
            from_fx=from_fx,
            from_amount=from_amount,
            to_account=to_account,
            to_currency=to_currency,
            to_fx=to_fx,
            to_amount=to_amount,
            instrument=instrument,
            trade_id=trade_id,
            description=description
        )
        self.record_flow(cash_flow)

    def record_account_fee(self, account_type: str,
                           from_currency: str, from_fx: Decimal, from_amount: Decimal,
                           to_currency: str, to_fx: Decimal, to_amount: Decimal,
                           timestamp: datetime,
                           trade_id: Optional[str] = None, instrument: Optional[str] = None,
                           description: Optional[str] = None) -> None:
        """Record fee-related cash flows"""
        cash_flow = CashFlow(
            timestamp=timestamp.isoformat(),
            flow_type=CashFlowType.ACCOUNT_FEE,
            from_account=account_type,
            from_currency=from_currency,
            from_fx=from_fx,
            from_amount=from_amount,
            to_account="EXTERNAL",
            to_currency=to_currency,
            to_fx=to_fx,
            to_amount=to_amount,
            instrument=instrument,
            trade_id=trade_id,
            description=description
        )
        self.record_flow(cash_flow)

    def get_current_flows(self) -> List[Dict[str, Any]]:
        """Get cash flows filtered by types with their raw values"""
        flows_data = []

        with self._lock:
            for flow in self.flows:
                flows_data.append(flow.to_dict())

        return flows_data