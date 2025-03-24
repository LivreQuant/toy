from dataclasses import dataclass, field
from typing import List, Optional
import time
import uuid

@dataclass
class Simulator:
    simulator_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    status: str = "ACTIVE"
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    initial_symbols: List[str] = field(default_factory=list)
    initial_cash: float = 100000.0

    def to_dict(self):
        return {
            'simulator_id': self.simulator_id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'status': self.status,
            'created_at': self.created_at,
            'last_active': self.last_active,
            'initial_symbols': self.initial_symbols,
            'initial_cash': self.initial_cash
        }