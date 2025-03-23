import time
import enum
import uuid
import json
from typing import Dict, List, Any, Optional, Set

class SessionStatus(enum.Enum):
    """Enum for session status"""
    CREATING = "CREATING"
    ACTIVE = "ACTIVE"
    RECONNECTING = "RECONNECTING"
    INACTIVE = "INACTIVE"
    EXPIRED = "EXPIRED"
    ERROR = "ERROR"

class SimulatorStatus(enum.Enum):
    """Enum for simulator status"""
    NONE = "NONE"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"

class ConnectionQuality(enum.Enum):
    """Enum for connection quality"""
    GOOD = "good"
    DEGRADED = "degraded"
    POOR = "poor"

class SessionState:
    """Model representing session state"""
    
    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id
        self.created_at = time.time()
        self.last_active = time.time()
        self.expires_at = time.time() + 3600  # 1 hour default
        self.status = SessionStatus.CREATING
        self.ip_address = None
        self.user_agent = None
        
        # Authentication
        self.token = None
        
        # Pod information
        self.pod_name = None
        self.pod_transferred = False
        self.previous_pod = None
        
        # Connection metrics
        self.connection_quality = ConnectionQuality.GOOD
        self.reconnect_count = 0
        self.frontend_connections = 0
        self.heartbeat_latency = None
        self.missed_heartbeats = 0
        
        # Simulator state
        self.simulator_id = None
        self.simulator_endpoint = None
        self.simulator_status = SimulatorStatus.NONE
        
        # Subscriptions
        self.subscriptions = {}  # type -> subscription info
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'created_at': self.created_at,
            'last_active': self.last_active,
            'expires_at': self.expires_at,
            'status': self.status.value,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'pod_name': self.pod_name,
            'pod_transferred': self.pod_transferred,
            'previous_pod': self.previous_pod,
            'connection_quality': self.connection_quality.value,
            'reconnect_count': self.reconnect_count,
            'frontend_connections': self.frontend_connections,
            'heartbeat_latency': self.heartbeat_latency,
            'missed_heartbeats': self.missed_heartbeats,
            'simulator_id': self.simulator_id,
            'simulator_endpoint': self.simulator_endpoint,
            'simulator_status': self.simulator_status.value,
            'subscriptions': self.subscriptions
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionState':
        """Create from dictionary representation"""
        session = cls(
            session_id=data['session_id'],
            user_id=data['user_id']
        )
        
        session.created_at = data.get('created_at', time.time())
        session.last_active = data.get('last_active', time.time())
        session.expires_at = data.get('expires_at', time.time() + 3600)
        session.status = SessionStatus(data.get('status', SessionStatus.ACTIVE.value))
        session.ip_address = data.get('ip_address')
        session.user_agent = data.get('user_agent')
        
        session.pod_name = data.get('pod_name')
        session.pod_transferred = data.get('pod_transferred', False)
        session.previous_pod = data.get('previous_pod')
        
        session.connection_quality = ConnectionQuality(
            data.get('connection_quality', ConnectionQuality.GOOD.value))
        session.reconnect_count = data.get('reconnect_count', 0)
        session.frontend_connections = data.get('frontend_connections', 0)
        session.heartbeat_latency = data.get('heartbeat_latency')
        session.missed_heartbeats = data.get('missed_heartbeats', 0)
        
        session.simulator_id = data.get('simulator_id')
        session.simulator_endpoint = data.get('simulator_endpoint')
        session.simulator_status = SimulatorStatus(
            data.get('simulator_status', SimulatorStatus.NONE.value))
        
        session.subscriptions = data.get('subscriptions', {})
        
        return session
    
    def update_activity(self):
        """Update last activity time"""
        self.last_active = time.time()
        
        # Reset expiration if getting close
        time_left = self.expires_at - time.time()
        if time_left < 1800:  # Less than 30 minutes
            self.expires_at = time.time() + 3600  # Reset to 1 hour
    
    def is_expired(self) -> bool:
        """Check if session is expired"""
        return time.time() > self.expires_at
    
    def update_connection_quality(self, latency_ms: int, missed_heartbeats: int) -> ConnectionQuality:
        """Update connection quality metrics and return new quality level"""
        self.heartbeat_latency = latency_ms
        self.missed_heartbeats = missed_heartbeats
        
        if missed_heartbeats >= 3:
            self.connection_quality = ConnectionQuality.POOR
        elif missed_heartbeats > 0 or latency_ms > 500:
            self.connection_quality = ConnectionQuality.DEGRADED
        else:
            self.connection_quality = ConnectionQuality.GOOD
        
        return self.connection_quality
    
    def start_simulator(self, simulator_id: str, simulator_endpoint: str):
        """Set simulator state to starting"""
        self.simulator_id = simulator_id
        self.simulator_endpoint = simulator_endpoint
        self.simulator_status = SimulatorStatus.STARTING
    
    def simulator_running(self):
        """Set simulator state to running"""
        self.simulator_status = SimulatorStatus.RUNNING
    
    def stop_simulator(self):
        """Set simulator state to stopping"""
        self.simulator_status = SimulatorStatus.STOPPING
    
    def simulator_stopped(self):
        """Clear simulator state"""
        self.simulator_status = SimulatorStatus.STOPPED
        # Don't clear IDs, just mark as stopped
    
    def clear_simulator(self):
        """Clear all simulator info"""
        self.simulator_id = None
        self.simulator_endpoint = None
        self.simulator_status = SimulatorStatus.NONE
    
    def handle_pod_transfer(self, new_pod: str):
        """Handle transfer to a new pod"""
        if self.pod_name and self.pod_name != new_pod:
            self.previous_pod = self.pod_name
            self.pod_name = new_pod
            self.pod_transferred = True
            self.reconnect_count += 1
        elif not self.pod_name:
            self.pod_name = new_pod
    
    def add_subscription(self, subscription_type: str, symbols: List[str]):
        """Add or update a subscription"""
        self.subscriptions[subscription_type] = {
            'symbols': symbols,
            'timestamp': time.time()
        }
    
    def remove_subscription(self, subscription_type: str):
        """Remove a subscription"""
        if subscription_type in self.subscriptions:
            del self.subscriptions[subscription_type]
    
    def get_subscription(self, subscription_type: str) -> Optional[Dict[str, Any]]:
        """Get a subscription by type"""
        return self.subscriptions.get(subscription_type)