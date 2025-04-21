"""
Session data models.
Defines the structure and state management for user sessions.
"""
import time
import uuid
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    """Session status enum"""
    ACTIVE = "ACTIVE"
    RECONNECTING = "RECONNECTING"
    INACTIVE = "INACTIVE"
    EXPIRED = "EXPIRED"
    ERROR = "ERROR"


class ConnectionQuality(str, Enum):
    """Connection quality enum"""
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    POOR = "POOR"


class Session(BaseModel):
    """Core Session model - essential session properties only"""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    status: SessionStatus = SessionStatus.INACTIVE
    created_at: float = Field(default_factory=time.time)
    last_active: float = Field(default_factory=time.time)
    expires_at: float = Field(default_factory=lambda: time.time() + 3600 * 12)
    token: Optional[str] = None

    def update_activity(self, extension_seconds: int = 3600):
        """Update last activity time and optionally extend expiry"""
        self.last_active = time.time()

        # Reset expiration
        self.expires_at = time.time() + extension_seconds

    def is_expired(self) -> bool:
        """Check if session is expired"""
        return time.time() > self.expires_at


class SessionDetails(BaseModel):
    """
    Session details model - separate from core session
    Stored in a dedicated table rather than as JSON
    """
    session_id: str
    user_id: str

    # Device and connection information
    device_id: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    pod_name: Optional[str] = None

    # Connection quality metrics
    connection_quality: ConnectionQuality = ConnectionQuality.GOOD
    heartbeat_latency: Optional[int] = None
    missed_heartbeats: int = 0
    reconnect_count: int = 0

    # Timestamps
    last_reconnect: Optional[float] = None
    last_device_update: Optional[float] = None
    last_quality_update: Optional[float] = None

    def update_connection_quality(self,
                                  latency_ms: int,
                                  missed_heartbeats: int) -> tuple:
        """
        Update connection quality metrics

        Returns:
            Tuple of (quality, reconnect_recommended)
        """
        self.heartbeat_latency = latency_ms
        self.missed_heartbeats = missed_heartbeats
        self.last_quality_update = time.time()

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

        self.connection_quality = quality
        self.updated_at = time.time()
        return quality.value, reconnect_recommended


class SessionWithDetails(BaseModel):
    """
    Combined view of session with details.
    Used for presenting a complete session view in the API.
    """
    session: Session
    details: SessionDetails

    @property
    def session_id(self) -> str:
        return self.session.session_id

    @property
    def user_id(self) -> str:
        return self.session.user_id

    @property
    def status(self) -> SessionStatus:
        return self.session.status

    @property
    def created_at(self) -> float:
        return self.session.created_at

    @property
    def expires_at(self) -> float:
        return self.session.expires_at

    @property
    def device_id(self) -> Optional[str]:
        return self.details.device_id

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            # Session core data
            "session_id": self.session.session_id,
            "status": self.session.status.value,
            "created_at": self.session.created_at,
            "last_active": self.session.last_active,
            "expires_at": self.session.expires_at,

            # Session details

            # Device and connection information
            "user_id": self.session.user_id,
            "device_id": self.details.device_id,
            "user_agent": self.details.user_agent,
            "ip_address": self.details.ip_address,
            "pod_name": self.details.pod_name,

            # Connection quality metrics
            "connection_quality": self.details.connection_quality,
            "heartbeat_latency": self.details.heartbeat_latency,
            "missed_heartbeats": self.details.missed_heartbeats,
            "reconnect_count": self.details.reconnect_count,

            # Timestamps
            "last_reconnect": self.details.last_reconnect,
            "last_device_update": self.details.last_device_update,
            "last_quality_update": self.details.last_quality_update,
        }

    @classmethod
    def from_components(cls, session: Session, details: SessionDetails) -> 'SessionWithDetails':
        """Create a SessionWithDetails from separate components"""
        return cls(session=session, details=details)
