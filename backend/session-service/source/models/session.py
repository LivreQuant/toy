"""
Session data models.
Defines the structure and state management for user sessions.
"""
import time
import uuid
from enum import Enum
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


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


class SimulatorStatus(str, Enum):
    """Simulator status enum"""
    NONE = "NONE"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class Subscription(BaseModel):
    """Data subscription model"""
    symbols: List[str] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)


class SessionMetadata(BaseModel):
    """Session metadata"""
    frontend_connections: int = 0
    last_ws_connection: Optional[float] = None
    last_sse_connection: Optional[float] = None
    reconnect_count: int = 0
    connection_quality: ConnectionQuality = ConnectionQuality.GOOD
    heartbeat_latency: Optional[int] = None
    missed_heartbeats: int = 0
    subscriptions: Dict[str, Subscription] = Field(default_factory=dict)
    device_id: Optional[str] = None
    simulator_id: Optional[str] = None
    simulator_endpoint: Optional[str] = None
    simulator_status: SimulatorStatus = SimulatorStatus.NONE
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    pod_name: Optional[str] = None
    pod_transferred: bool = False
    previous_pod: Optional[str] = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class Session(BaseModel):
    """Session model"""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    status: SessionStatus = SessionStatus.CREATING
    created_at: float = Field(default_factory=time.time)
    last_active: float = Field(default_factory=time.time)
    expires_at: float = Field(default_factory=lambda: time.time() + 3600)
    metadata: SessionMetadata = Field(default_factory=SessionMetadata)
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
                                  missed_heartbeats: int,
                                  connection_type: str = "websocket") -> tuple:
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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "expires_at": self.expires_at,
            **self.metadata.dict()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Session':
        """Create a Session from a dictionary"""
        # Extract metadata fields
        metadata_dict = {}
        session_dict = {}

        # Sort fields into session and metadata
        for key, value in data.items():
            if key in ['session_id', 'user_id', 'status', 'created_at',
                       'last_active', 'expires_at', 'token']:
                session_dict[key] = value
            else:
                metadata_dict[key] = value

        # Convert enums
        if 'status' in session_dict and isinstance(session_dict['status'], str):
            session_dict['status'] = SessionStatus(session_dict['status'])

        if 'connection_quality' in metadata_dict and isinstance(metadata_dict['connection_quality'], str):
            metadata_dict['connection_quality'] = ConnectionQuality(metadata_dict['connection_quality'])

        if 'simulator_status' in metadata_dict and isinstance(metadata_dict['simulator_status'], str):
            metadata_dict['simulator_status'] = SimulatorStatus(metadata_dict['simulator_status'])

        # Convert subscriptions
        if 'subscriptions' in metadata_dict and isinstance(metadata_dict['subscriptions'], dict):
            subscriptions = {}
            for key, value in metadata_dict['subscriptions'].items():
                if isinstance(value, dict):
                    subscriptions[key] = Subscription(**value)
                else:
                    subscriptions[key] = value
            metadata_dict['subscriptions'] = subscriptions

        # Create session with metadata
        session_dict['metadata'] = SessionMetadata(**metadata_dict)
        return cls(**session_dict)
