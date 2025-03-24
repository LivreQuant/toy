import time
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

class SessionStatus:
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

@dataclass
class SessionInfo:
    session_id: str
    user_id: str
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    status: str = SessionStatus.ACTIVE
    symbols: List[str] = field(default_factory=list)
    
    def update_activity(self):
        """Update the last activity timestamp"""
        self.last_active = time.time()
    
    def is_inactive(self, timeout_seconds: int) -> bool:
        """Check if session is inactive based on timeout"""
        return time.time() - self.last_active > timeout_seconds