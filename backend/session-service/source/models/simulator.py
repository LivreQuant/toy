"""
Simulator data models.
Defines the structure for exchange simulator instances.
"""
import time
import uuid
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class SimulatorStatus(str, Enum):
    """Simulator status enum"""
    NONE = "NONE"
    CREATING = "CREATING"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class Simulator(BaseModel):
    """Exchange simulator model"""
    simulator_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    status: SimulatorStatus = SimulatorStatus.CREATING
    endpoint: Optional[str] = None
    created_at: float = Field(default_factory=time.time)
    last_active: float = Field(default_factory=time.time)

    def update_activity(self):
        """Update last activity timestamp"""
        self.last_active = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "simulator_id": self.simulator_id,
            "session_id": self.session_id,
            "status": self.status.value,
            "endpoint": self.endpoint,
            "created_at": self.created_at,
            "last_active": self.last_active,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Simulator':
        """Create from dictionary"""
        # Convert status string to enum if needed
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = SimulatorStatus(data['status'])

        return cls(**data)
