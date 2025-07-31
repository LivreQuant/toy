# source/simulation/managers/impact.py
from dataclasses import dataclass
from typing import Dict, Optional, List
from datetime import datetime
from decimal import Decimal
from source.simulation.managers.utils import TrackingManager


@dataclass
class ImpactState:
    symbol: str
    trade_id: Optional[str]
    current_impact: Decimal
    previous_impact: Decimal
    currency: str
    base_price: Decimal
    impacted_price: Decimal
    cumulative_volume: int
    trade_volume: int
    start_timestamp: Optional[str]
    end_timestamp: Optional[str]
    impact_type: str = "decay"

    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'trade_id': self.trade_id if self.trade_id else '',
            'previous_impact': float(self.previous_impact),
            'current_impact': float(self.current_impact),
            'currency': self.currency,
            'base_price': float(self.base_price),
            'impacted_price': float(self.impacted_price),
            'cumulative_volume': self.cumulative_volume,
            'trade_volume': self.trade_volume,
            'start_timestamp': self.start_timestamp if self.start_timestamp else '',
            'end_timestamp': self.end_timestamp if self.end_timestamp else '',
            'impact_type': self.impact_type
        }


class ImpactManager(TrackingManager):
    def __init__(self, tracking: bool = False, decay_rate: float = 0.1):
        headers = [
            'timestamp', 'symbol', 'trade_id', 'previous_impact',
            'current_impact', 'currency', 'base_price', 'impacted_price',
            'cumulative_volume', 'trade_volume', 'start_timestamp', 'end_timestamp',
            'impact_type'
        ]

        super().__init__(
            manager_name="ImpactManager",
            table_name="impact_data",
            headers=headers,
            tracking=tracking
        )

        self.impacts: Dict[str, ImpactState] = {}
        self._decay_rate = decay_rate

    def _prepare_impact_data(self, timestamp: datetime) -> List[Dict]:
        """Prepare impact data for storage"""
        snapshot_data = []
        with self._lock:
            for impact in self.impacts.values():
                snapshot_data.append({
                    'timestamp': timestamp.isoformat(),
                    **impact.to_dict()
                })
        return snapshot_data

    def initialize_impacts(self, impacts: Dict[str, ImpactState], timestamp: datetime) -> None:
        """Initialize impacts from last snapshot - no SOD file writing"""
        with self._lock:
            self.impacts = impacts.copy()

    def update_impact(self, symbol: str, currency: str, base_price: Decimal,
                      impacted_price: Decimal, trade_volume: int, total_volume: int,
                      start_timestamp: datetime, end_timestamp: datetime,
                      trade_id: Optional[str] = None, impact_type: str = "decay") -> Decimal:

        with self._lock:
            # Get previous impact
            previous_impact = Decimal('0')
            if symbol in self.impacts:
                previous_impact = self.impacts[symbol].current_impact

            # Calculate current impact percentage
            current_impact = (impacted_price / base_price) - Decimal('1')

            from source.utils.timezone_utils import to_iso_string

            # Update state
            self.impacts[symbol] = ImpactState(
                symbol=symbol,
                trade_id=trade_id,
                current_impact=current_impact,
                previous_impact=previous_impact,
                currency=currency,
                base_price=base_price,
                impacted_price=impacted_price,
                cumulative_volume=total_volume,
                trade_volume=trade_volume,
                start_timestamp=to_iso_string(start_timestamp),
                end_timestamp=to_iso_string(end_timestamp),
                impact_type=impact_type
            )

            # Write to storage
            if self.tracking:
                data = self._prepare_impact_data(end_timestamp)
                self.write_to_storage(data, timestamp=end_timestamp)

            return impacted_price

    def get_impact(self, symbol: str) -> Optional[ImpactState]:
        """Get impact state for a symbol"""
        with self._lock:
            return self.impacts.get(symbol)

    def get_all_impacts(self) -> Dict[str, ImpactState]:
        """Get all current impacts"""
        with self._lock:
            return self.impacts.copy()