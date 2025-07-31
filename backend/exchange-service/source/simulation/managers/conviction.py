# source/simulation/managers/conviction.py
from threading import RLock
from typing import Dict, Optional, List
from datetime import datetime
import logging
from source.simulation.managers.utils import TrackingManager


class ConvictionManager(TrackingManager):
    def __init__(self, tracking: bool = False):
        headers = [
            'timestamp', 'conviction_id', 'broker_id', 'instrument_id', 'side',
            'quantity', 'currency', 'participation_rate', 'tag', 'score',
            'zscore', 'target_percentage', 'target_notional', 'horizon_zscore',
            'status', 'submit_time', 'cancel_time'
        ]

        super().__init__(
            manager_name="ConvictionManager",
            table_name="convictions",
            headers=headers,
            tracking=tracking
        )

        self._convictions: Dict[str, Dict] = {}

    def _prepare_conviction_data(self, conviction_data: Dict) -> List[Dict]:
        """Prepare conviction data for storage"""
        from source.utils.timezone_utils import to_iso_string

        return [{
            'timestamp': to_iso_string(datetime.utcnow()),
            'conviction_id': conviction_data.get('conviction_id', ''),
            'broker_id': conviction_data.get('broker_id', ''),
            'instrument_id': conviction_data.get('instrument_id', ''),
            'side': conviction_data.get('side', ''),
            'quantity': conviction_data.get('quantity', 0),
            'currency': conviction_data.get('currency', ''),
            'participation_rate': conviction_data.get('participation_rate', 0.0),
            'tag': conviction_data.get('tag', ''),
            'score': conviction_data.get('score', 0.0),
            'zscore': conviction_data.get('zscore', 0.0),
            'target_percentage': conviction_data.get('target_percentage', 0.0),
            'target_notional': conviction_data.get('target_notional', 0.0),
            'horizon_zscore': conviction_data.get('horizon_zscore', 0.0),
            'status': conviction_data.get('status', 'ACTIVE'),
            'submit_time': to_iso_string(conviction_data.get('submit_time', datetime.utcnow())),
            'cancel_time': to_iso_string(conviction_data.get('cancel_time')) if conviction_data.get(
                'cancel_time') else ''
        }]

    def add_conviction(self, conviction_data: Dict) -> None:
        """Add a new conviction"""
        with self._lock:
            conviction_id = conviction_data['conviction_id']
            self._convictions[conviction_id] = conviction_data

            # Write to storage
            if self.tracking:
                data = self._prepare_conviction_data(conviction_data)
                self.write_to_storage(data)

    def cancel_conviction(self, conviction_id: str, cancel_time: datetime) -> bool:
        """Cancel an existing conviction"""
        with self._lock:
            if conviction_id not in self._convictions:
                return False

            conviction = self._convictions[conviction_id]
            conviction['status'] = 'CANCELLED'
            conviction['cancel_time'] = cancel_time

            # Write to storage
            if self.tracking:
                data = self._prepare_conviction_data(conviction)
                self.write_to_storage(data)

        return True

    def get_conviction(self, conviction_id: str) -> Optional[Dict]:
        """Get a specific conviction"""
        with self._lock:
            return self._convictions.get(conviction_id)

    def get_active_convictions(self) -> Dict[str, Dict]:
        """Get all active convictions"""
        with self._lock:
            return {k: v for k, v in self._convictions.items() if v['status'] == 'ACTIVE'}

    def get_all_convictions(self) -> Dict[str, Dict]:
        """Get all convictions"""
        with self._lock:
            return self._convictions.copy()