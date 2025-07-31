# source/orchestration/replay/replay_types.py
"""
Base types and state management for replay functionality
"""

from datetime import datetime
from typing import Optional
from dataclasses import dataclass
from enum import Enum


class ReplayModeState(Enum):
    """States for replay mode operation"""
    LIVE = "live"
    REPLAY_WAITING = "replay_waiting"
    REPLAY_PROCESSING = "replay_processing"
    REPLAY_COMPLETE = "replay_complete"
    ERROR = "error"


@dataclass
class ReplayProgress:
    """Progress information for replay mode"""
    current_time: datetime
    target_time: datetime
    total_minutes: int
    completed_minutes: int
    remaining_minutes: int
    state: ReplayModeState
    last_updated: datetime
    error_message: Optional[str] = None

    @property
    def progress_percentage(self) -> float:
        """Calculate completion percentage"""
        if self.total_minutes == 0:
            return 100.0
        return (self.completed_minutes / self.total_minutes) * 100.0
