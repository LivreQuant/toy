"""
Session data models.
Defines the structure and state management for user sessions.
"""
import time
import uuid
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

from source.models.simulator import Simulator, SimulatorStatus


class SessionStatus(str, Enum):
    """Session status enum"""
    CREATING = "CREATING"
    ACTIVE = "ACTIVE"
    RECONNECTING = "RECONNECTING"
    INACTIVE = "INACTIVE"
    EXPIRED = "EXPIRED"
    ERROR = "ERROR"


class ConnectionQuality(str, Enum):
    """Connection quality enum"""
    GOOD = "good"
    DEGRADED = "degraded"
    POOR = "poor"


class SessionMetadata(BaseModel):
    """Session metadata"""
    device_id: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    pod_name: Optional[str] = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    connection_quality: ConnectionQuality = ConnectionQuality.GOOD
    heartbeat_latency: Optional[int] = None
    missed_heartbeats: int = 0


class Session(BaseModel):
    """Session model"""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    status: SessionStatus = SessionStatus.CREATING
    created_at: float = Field(default_factory=time.time)
    last_active: float = Field(default_factory=time.time)
    expires_at: float = Field(default_factory=lambda: time.time() + 3600)
    metadata: SessionMetadata = Field(default_factory=SessionMetadata)
    simulator: Optional[Simulator] = None
    token: Optional[str] = None

    def update_activity(self, extension_seconds: int = 3600):
        """Update last activity time and optionally extend expiry"""
        self.last_active = time.time()
        self.metadata.updated_at = time.time()

        # Reset expiration
        self.expires_at = time.time() + extension_seconds

    def is_expired(self) -> bool:
        """Check if session is expired"""
        return time.time() > self.expires_at

    def update_connection_quality(self,
                                  latency_ms: int,
                                  missed_heartbeats: int) -> tuple:
        """
        Update connection quality metrics

        Returns:
            Tuple of (quality, reconnect_recommended)
        """
        self.metadata.heartbeat_latency = latency_ms
        self.metadata.missed_heartbeats = missed_heartbeats

        # Determine connection quality
        if missed_heartbeats >= 3:
            quality = ConnectionQuality.POOR
            reconnect_recommended = True
        elif missed_heartbeats > 0 or latency_ms > 500:
            quality = ConnectionQuality.DEGRADED
            reconnect_recommended = False
        else:
            quality = ConnectionQuality.GOOD
            reconnect_recommended = False

        self.metadata.connection_quality = quality
        return quality.value, reconnect_recommended

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        base_dict = {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "expires_at": self.expires_at,
            "token": self.token,
            **self.metadata.dict()
        }

        # Include simulator if exists
        if self.simulator:
            base_dict['simulator'] = self.simulator.to_dict()

        return base_dict

    @classmethod
    def from_dict(cls, data: dict) -> 'Session':
        """Create a Session from a dictionary"""
        # Extract simulator data if present
        simulator_data = data.pop('simulator', None)

        # Convert status enum
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = SessionStatus(data['status'])

        # Convert connection quality
        if 'connection_quality' in data and isinstance(data['connection_quality'], str):
            data['connection_quality'] = ConnectionQuality(data['connection_quality'])

        # Create session
        session = cls(**data)

        # Add simulator if data exists
        if simulator_data:
            session.simulator = Simulator.from_dict(simulator_data)

        return session