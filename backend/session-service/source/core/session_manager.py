"""
Session manager for handling user sessions.
Manages user sessions, authentication, and coordinates with simulator manager.
"""
import logging
import time
import asyncio
import json
from typing import Dict, Any, Optional, Tuple, List
from opentelemetry import trace

from source.models.session import Session, SessionStatus, SimulatorStatus
from source.db.session_store import DatabaseManager
from source.api.clients.auth_client import AuthClient
from source.api.clients.exchange_client import ExchangeClient
from source.core.simulator_manager import SimulatorManager
from source.config import config

from source.utils.metrics import (
    track_session_count, track_session_operation, track_session_ended,
    track_simulator_count, track_simulator_operation, track_connection_quality
)
from source.utils.tracing import optional_trace_span

logger = logging.getLogger('session_manager')

class SessionManager:
    """Manager for user sessions"""
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        auth_client: AuthClient,
        exchange_client: ExchangeClient,
        redis_client = None
    ):
        """
        Initialize session manager
        
        Args:
            db_manager: Database manager for session persistence
            auth_client: Authentication client for token validation
            exchange_client: Exchange client for simulator communication
            redis_client: Optional Redis client for pub/sub and caching
        """
        self.db_manager = db_manager
        self.auth_client = auth_client
        self.exchange_client = exchange_client
        self.redis = redis_client
        self.pod_name = config.kubernetes.pod_name
        
        # Create simulator manager
        self.simulator_manager = SimulatorManager(db_manager, exchange_client)
        
        # Background tasks
        self.cleanup_task = None

        # Create tracer
        self.tracer = trace.get_tracer("session_manager")

    async def start_cleanup_task(self):
        """Start background cleanup task"""
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop_cleanup_task(self):
        """Stop background cleanup task"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
    
    async def _cleanup_loop(self):
        """Background loop for periodic cleanup tasks"""
        while True:
            try:
                # Cleanup expired sessions
                await self.db_manager.cleanup_expired_sessions()
                
                # Cleanup inactive simulators
                await self.simulator_manager.cleanup_inactive_simulators()
                
                # Sleep until next cleanup cycle (every 15 minutes)
                await asyncio.sleep(900)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(60)  # Shorter interval on error
    
    async def create_session(self, user_id: str, token: str, ip_address: Optional[str] = None) -> Tuple[Optional[str], bool]:
        """
        Create a new session for a user
        
        Args:
            user_id: The user ID
            token: Authentication token
            ip_address: Client IP address
            
        Returns:
            Tuple of (session_id, is_new)
        """
        with optional_trace_span(self.tracer, "create_session") as span:
            span.set_attribute("user_id", user_id)
            span.set_attribute("ip_address", ip_address)

            # Validate token
            validation = await self.auth_client.validate_token(token)

            if not validation.get('valid', False):
                logger.warning(f"Invalid token for user {user_id}")
                span.set_attribute("token_valid", False)
                return None, False

            # Make sure user in token matches provided user_id
            token_user_id = validation.get('user_id')
            span.set_attribute("token_user_id", token_user_id)

            logger.warning(f"COMPARE: {token_user_id} | {user_id}")

            if token_user_id != user_id:
                logger.warning(f"Token user_id {token_user_id} doesn't match provided user_id {user_id}")
                span.set_attribute("user_id_match", False)
                span.set_attribute("error", "User ID mismatch")
                return None, False

            # Create session in database
            try:
                session_id, is_new = await self.db_manager.create_session(user_id, ip_address)

                if is_new:
                    # Set additional metadata
                    await self.db_manager.update_session_metadata(session_id, {
                        'pod_name': self.pod_name,
                        'ip_address': ip_address
                    })

                    # Track session creation
                    track_session_operation("create_new")

                    # Publish session creation event if Redis is available
                    if self.redis:
                        await self.redis.publish('session_events', json.dumps({
                            'type': 'session_created',
                            'session_id': session_id,
                            'user_id': user_id,
                            'pod_name': self.pod_name,
                            'timestamp': time.time()
                        }))
                else:
                    # Track session reuse
                    track_session_operation("create_existing")

                span.set_attribute("session_id", session_id)
                span.set_attribute("is_new", is_new)

                # Update active session count metric
                active_sessions = await self.db_manager.get_active_session_count()
                track_session_count(active_sessions)

                return session_id, is_new
            except Exception as e:
                logger.error(f"Error creating session: {e}")
                span.record_exception(e)
                return None, False
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session details
        
        Args:
            session_id: The session ID
            
        Returns:
            Session details dict if found, None otherwise
        """
        try:
            session = await self.db_manager.get_session(session_id)
            
            if not session:
                return None
            
            return session.to_dict()
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            return None
    
    async def validate_session(self, session_id: str, token: str) -> Optional[str]:
        """
        Validate session and token
        
        Args:
            session_id: The session ID
            token: Authentication token
            
        Returns:
            User ID if valid, None otherwise
        """
        # Validate token
        validation = await self.auth_client.validate_token(token)

        logger.info(f"VALIDATION RESULTS: {validation}")
        
        if not validation.get('valid', False):
            logger.warning(f"Invalid token for session {session_id}")
            return None
        
        # Get user ID from token validation
        user_id = validation.get('userId')
        
        # Get session from database
        session = await self.db_manager.get_session(session_id)
        
        if not session:
            logger.warning(f"Session {session_id} not found")
            return None
        
        # Check if session belongs to user
        if session.user_id != user_id:
            logger.warning(f"Session {session_id} does not belong to user {user_id}")
            return None
        
        # Check if session is expired
        if session.is_expired():
            logger.warning(f"Session {session_id} has expired")
            return None
        
        # Update session activity
        session.update_activity()
        await self.db_manager.update_session_activity(session_id)
        
        return user_id
    
    async def end_session(self, session_id: str, token: str) -> Tuple[bool, str]:
        """
        End a session
        
        Args:
            session_id: The session ID
            token: Authentication token
            
        Returns:
            Tuple of (success, error_message)
        """
        with optional_trace_span(self.tracer, "end_session") as span:
            span.set_attribute("session_id", session_id)

            # Validate session
            user_id = await self.validate_session(session_id, token)
            span.set_attribute("user_id", user_id)
            span.set_attribute("session_valid", user_id is not None)

            if not user_id:
                span.set_attribute("error", "Invalid session or token")
                return False, "Invalid session or token"

            try:
                # Get current session details
                session = await self.db_manager.get_session(session_id)
                session_created_at = session.created_at

                # Stop simulator if active
                if session.metadata.simulator_id:
                    simulator_id = session.metadata.simulator_id
                    span.set_attribute("simulator_id", simulator_id)

                    await self.simulator_manager.stop_simulator(session.metadata.simulator_id)
                    track_simulator_operation("stop_on_session_end")

                # End session in database
                success = await self.db_manager.end_session(session_id)

                if not success:
                    span.set_attribute("error", "Failed to end session")
                    return False, "Failed to end session"

                # Calculate session lifetime and record metric
                lifetime = time.time() - session_created_at
                track_session_ended(lifetime, "completed")
                track_session_operation("end")

                # Update active session count
                active_sessions = await self.db_manager.get_active_session_count()
                track_session_count(active_sessions)

                # Publish session end event if Redis is available
                if self.redis:
                    await self.redis.publish('session_events', json.dumps({
                        'type': 'session_ended',
                        'session_id': session_id,
                        'user_id': user_id,
                        'pod_name': self.pod_name,
                        'timestamp': time.time()
                    }))

                return True, ""
            except Exception as e:
                logger.error(f"Error ending session: {e}")
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return False, str(e)
    
    async def update_connection_quality(
        self, 
        session_id: str, 
        token: str, 
        metrics: Dict[str, Any]
    ) -> Tuple[str, bool]:
        """
        Update connection quality metrics
        
        Args:
            session_id: The session ID
            token: Authentication token
            metrics: Connection metrics dict
            
        Returns:
            Tuple of (quality, reconnect_recommended)
        """
        with optional_trace_span(self.tracer, "update_connection_quality") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("latency_ms", metrics.get('latency_ms', 0))
            span.set_attribute("missed_heartbeats", metrics.get('missed_heartbeats', 0))
            span.set_attribute("connection_type", metrics.get('connection_type', 'websocket'))

            # Validate session
            user_id = await self.validate_session(session_id, token)
            span.set_attribute("user_id", user_id)
            span.set_attribute("session_valid", user_id is not None)

            if not user_id:
                span.set_attribute("error", "Invalid session or token")
                return "unknown", False

            try:
                # Get session details
                session = await self.db_manager.get_session(session_id)

                # Update metrics
                quality, reconnect_recommended = session.update_connection_quality(
                    metrics.get('latency_ms', 0),
                    metrics.get('missed_heartbeats', 0),
                    metrics.get('connection_type', 'websocket')
                )

                # Update database
                await self.db_manager.update_session_metadata(session_id, {
                    'connection_quality': quality,
                    'heartbeat_latency': metrics.get('latency_ms'),
                    'missed_heartbeats': metrics.get('missed_heartbeats')
                })

                # Track connection quality metric
                track_connection_quality(quality)

                span.set_attribute("quality", quality)
                span.set_attribute("reconnect_recommended", reconnect_recommended)

                return quality, reconnect_recommended
            except Exception as e:
                logger.error(f"Error updating connection quality: {e}")
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return "unknown", False

    async def start_simulator(self, session_id: str, token: str) -> Tuple[Optional[str], Optional[str], str]:
        """
        Start a simulator for a session
        
        Args:
            session_id: The session ID
            token: Authentication token
            
        Returns:
            Tuple of (simulator_id, endpoint, error_message)
        """
        # Validate session
        user_id = await self.validate_session(session_id, token)
        
        if not user_id:
            return None, None, "Invalid session or token"
        
        try:
            # Get session
            session = await self.db_manager.get_session(session_id)
            
            # Check if there's already an active simulator
            if session.metadata.simulator_id and session.metadata.simulator_status != SimulatorStatus.STOPPED:
                # Verify simulator is actually running
                status = await self.simulator_manager.get_simulator_status(session.metadata.simulator_id)
                
                if status['status'] in ['RUNNING', 'STARTING']:
                    return session.metadata.simulator_id, session.metadata.simulator_endpoint, ""
            
            # Get subscription symbols from session metadata
            symbols = []
            for sub_type, subscription in session.metadata.subscriptions.items():
                if hasattr(subscription, 'symbols'):
                    symbols.extend(subscription.symbols)
            
            # Create new simulator
            simulator, error = await self.simulator_manager.create_simulator(
                session_id, 
                user_id,
                symbols if symbols else None
            )
            
            if not simulator:
                return None, None, error
            
            # Update session metadata
            await self.db_manager.update_session_metadata(session_id, {
                'simulator_id': simulator.simulator_id,
                'simulator_endpoint': simulator.endpoint,
                'simulator_status': simulator.status.value
            })
            
            # Publish simulator started event if Redis is available
            if self.redis:
                await self.redis.publish('session_events', json.dumps({
                    'type': 'simulator_started',
                    'session_id': session_id,
                    'simulator_id': simulator.simulator_id,
                    'pod_name': self.pod_name,
                    'timestamp': time.time()
                }))
            
            return simulator.simulator_id, simulator.endpoint, ""
        except Exception as e:
            logger.error(f"Error starting simulator: {e}")
            return None, None, str(e)
    
    async def stop_simulator(self, session_id: str, token: str) -> Tuple[bool, str]:
        """
        Stop the simulator for a session
        
        Args:
            session_id: The session ID
            token: Authentication token
            
        Returns:
            Tuple of (success, error_message)
        """
        # Validate session
        user_id = await self.validate_session(session_id, token)
        
        if not user_id:
            return False, "Invalid session or token"
        
        try:
            # Get session
            session = await self.db_manager.get_session(session_id)
            
            # Check if there's an active simulator
            if not session.metadata.simulator_id:
                return False, "No active simulator for this session"
            
            # Stop simulator
            success, error = await self.simulator_manager.stop_simulator(session.metadata.simulator_id)
            
            if not success:
                return False, error
            
            # Update session metadata
            await self.db_manager.update_session_metadata(session_id, {
                'simulator_status': SimulatorStatus.STOPPED.value
            })
            
            # Publish simulator stopped event if Redis is available
            if self.redis:
                await self.redis.publish('session_events', json.dumps({
                    'type': 'simulator_stopped',
                    'session_id': session_id,
                    'simulator_id': session.metadata.simulator_id,
                    'pod_name': self.pod_name,
                    'timestamp': time.time()
                }))
            
            return True, ""
        except Exception as e:
            logger.error(f"Error stopping simulator: {e}")
            return False, str(e)
    
    async def reconnect_session(self, session_id: str, token: str, attempt: int = 1) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Reconnect to a session, potentially restarting a simulator
        
        Args:
            session_id: The session ID
            token: Authentication token
            attempt: Reconnection attempt number
            
        Returns:
            Tuple of (session_dict, error_message)
        """
        # Validate session
        user_id = await self.validate_session(session_id, token)
        
        if not user_id:
            return None, "Invalid session or token"
        
        try:
            # Get session
            session = await self.db_manager.get_session(session_id)
            
            # Check if simulator needs restart
            simulator_needs_restart = False
            
            if session.metadata.simulator_id:
                # Check simulator status
                status = await self.simulator_manager.get_simulator_status(session.metadata.simulator_id)
                
                if status['status'] not in ['RUNNING', 'STARTING']:
                    simulator_needs_restart = True
            
            # Restart simulator if needed
            if simulator_needs_restart:
                simulator_id, endpoint, error = await self.start_simulator(session_id, token)
                
                if error:
                    logger.warning(f"Failed to restart simulator during reconnect: {error}")
            
            # Update session metadata
            await self.db_manager.update_session_metadata(session_id, {
                'reconnect_count': session.metadata.reconnect_count + 1,
                'last_reconnect': time.time()
            })
            
            # Get updated session
            session = await self.db_manager.get_session(session_id)
            
            return session.to_dict(), ""
        except Exception as e:
            logger.error(f"Error reconnecting session: {e}")
            return None, str(e)