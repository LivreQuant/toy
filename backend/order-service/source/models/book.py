from dataclasses import dataclass, field
from typing import Optional
import time
import uuid


@dataclass
class Book:
    """Book model representing a trading configuration"""
    user_id: str
    name: str
    initial_capital: float
    risk_level: str  # 'low', 'medium', 'high'
    market_focus: Optional[str] = None  # e.g., 'technology', 'healthcare'
    book_id: Optional[str] = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = 'CONFIGURED'  # 'CONFIGURED', 'ACTIVE', 'ARCHIVED'
    trading_strategy: Optional[str] = None
    max_position_size: Optional[float] = None
    max_total_risk: Optional[float] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
