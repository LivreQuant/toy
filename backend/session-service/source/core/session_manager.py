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
    track_simulator_count, track_simulator_operation, track_connection_quality,
    track_cleanup_operation
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
        # Add heartbeat task
        self.heartbeat_task = asyncio.create_task(self._simulator_heartbeat_loop())
        
    async def _simulator_heartbeat_loop(self):
        """Send periodic heartbeats to active simulators"""
        while True:
            try:
                # Get all active simulator endpoints
                active_sessions = await self.db_manager.get_active_sessions()
                
                heartbeat_tasks = []
                for session in active_sessions:
                    # Check if session has an active simulator
                    sim_id = getattr(session.metadata, 'simulator_id', None)
                    sim_endpoint = getattr(session.metadata, 'simulator_endpoint', None)
                    
                    if sim_id and sim_endpoint:
                        task = asyncio.create_task(
                            self._send_simulator_heartbeat(
                                session.session_id, 
                                sim_id, 
                                sim_endpoint
                            )
                        )
                        heartbeat_tasks.append(task)
                
                # Wait for all heartbeats to complete
                if heartbeat_tasks:
                    await asyncio.gather(*heartbeat_tasks, return_exceptions=True)
                    
                # Sleep until next heartbeat cycle (every 15 seconds)
                await asyncio.sleep(15)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in simulator heartbeat loop: {e}")
                await asyncio.sleep(5)  # Shorter sleep on error

    async def _send_simulator_heartbeat(self, session_id, simulator_id, endpoint):
        """Send heartbeat to a specific simulator"""
        try:
            result = await self.exchange_client.heartbeat(
                endpoint, 
                session_id, 
                f"heartbeat-{self.pod_name}"
            )
            
            # Update last heartbeat timestamp if successful
            if result.get('success'):
                await self.db_manager.update_simulator_last_active(
                    simulator_id,
                    time.time()
                )
                return True
            else:
                logger.warning(f"Failed to send heartbeat to simulator {simulator_id}: {result.get('error')}")
                return False
        except Exception as e:
            logger.error(f"Error sending heartbeat to simulator {simulator_id}: {e}")
            return False

    async def stop_cleanup_task(self):
        """Stop background cleanup task"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Cancel heartbeat task as well
        if hasattr(self, 'heartbeat_task') and self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
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
                
                # Enhanced: Cleanup zombie sessions
                await self._cleanup_zombie_sessions()
                
                # Sleep until next cleanup cycle (every 15 minutes)
                await asyncio.sleep(900)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(60)  # Shorter interval on error

    async def _cleanup_zombie_sessions(self):
        """Identify and cleanup sessions that are still active but clients haven't connected in a long time"""
        try:
            # Define thresholds for zombie detection
            heartbeat_missing_threshold = time.time() - (config.websocket.heartbeat_interval * 10)
            connection_missing_threshold = time.time() - 3600  # 1 hour with no connections
                
            # Get all active sessions
            active_sessions = await self.db_manager.get_active_sessions()
            
            zombie_count = 0
            for session in active_sessions:
                # Skip sessions with recent activity
                if session.last_active > heartbeat_missing_threshold:
                    continue
                    
                # Skip sessions with recent WebSocket or SSE connections
                last_ws_connection = session.metadata.last_ws_connection if hasattr(session.metadata, 'last_ws_connection') else 0
                last_sse_connection = session.metadata.last_sse_connection if hasattr(session.metadata, 'last_sse_connection') else 0
                
                if max(last_ws_connection, last_sse_connection) > connection_missing_threshold:
                    continue
                    
                # This session appears to be a zombie
                logger.info(f"Cleaning up zombie session {session.session_id}, "
                        f"last active: {session.last_active}")
                
                # Stop any running simulators
                if hasattr(session.metadata, 'simulator_id') and session.metadata.simulator_id:
                    try:
                        await self.stop_simulator(session.session_id, None, force=True)
                    except Exception as e:
                        logger.error(f"Error stopping simulator for zombie session: {e}")
                
                # Mark session as expired
                await self.db_manager.update_session_status(session.session_id, SessionStatus.EXPIRED.value)
                zombie_count += 1
            
            if zombie_count > 0:
                logger.info(f"Cleaned up {zombie_count} zombie sessions")
                track_cleanup_operation("zombie_sessions", zombie_count)
        
        except Exception as e:
            logger.error(f"Error cleaning up zombie sessions: {e}")
            
    async def transfer_session_ownership(self, session_id: str, new_pod_name: str) -> bool:
        """Transfer ownership of a session to another pod during migration"""
        with optional_trace_span(self.tracer, "transfer_session_ownership") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("new_pod_name", new_pod_name)
            
            session = await self.db_manager.get_session(session_id)
            if not session:
                span.set_attribute("error", "Session not found")
                return False
                
            # Record handoff in progress
            await self.db_manager.update_session_metadata(session_id, {
                'pod_transferred': True,
                'previous_pod': session.metadata.pod_name,
                'pod_name': new_pod_name,
                'transfer_timestamp': time.time()
            })
            
            # Notify clients of migration via WebSocket
            if self.websocket_manager:
                await self.websocket_manager.broadcast_to_session(session_id, {
                    'type': 'session_migration',
                    'new_pod': new_pod_name
                })
            
            # Publish migration event to Redis for other pods
            if self.redis:
                await self.redis.publish('session_events', json.dumps({
                    'type': 'session_migrated',
                    'session_id': session_id,
                    'previous_pod': session.metadata.pod_name,
                    'new_pod': new_pod_name,
                    'timestamp': time.time()
                }))
            
            return True

    async def _run_simulator_heartbeat_task(self):
        """Background task to send heartbeats to all active simulators"""
        while True:
            try:
                # Get all active sessions with simulators
                active_sessions = await self.db_manager.get_active_sessions_with_simulators()
                
                for session in active_sessions:
                    if not session.metadata.simulator_id or not session.metadata.simulator_endpoint:
                        continue
                        
                    # Send heartbeat with TTL
                    result = await self.exchange_client.send_heartbeat_with_ttl(
                        session.metadata.simulator_endpoint,
                        session.session_id,
                        f"heartbeat-{self.pod_name}",
                        ttl_seconds=60  # Simulator will shutdown if no heartbeat for 60 seconds
                    )
                    
                    # Update metadata if successful
                    if result.get('success'):
                        await self.db_manager.update_session_metadata(session.session_id, {
                            'last_simulator_heartbeat': time.time()
                        })
                    else:
                        # Log error and mark for investigation
                        logger.warning(f"Failed to send heartbeat to simulator {session.metadata.simulator_id}: {result.get('error')}")
                
                # Wait before next heartbeat round
                await asyncio.sleep(15)  # Send heartbeats every 15 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in simulator heartbeat task: {e}")
                await asyncio.sleep(5)  # Shorter interval on error
                    
    async def create_session(self, user_id: str, device_id: str, token: str, ip_address: Optional[str] = None) -> Tuple[Optional[str], bool]:
        """
        Create a new session for a user with device ID
        
        Args:
            user_id: The user ID
            device_id: The device ID
            token: Authentication token
            ip_address: Client IP address
            
        Returns:
            Tuple of (session_id, is_new)
        """
        with optional_trace_span(self.tracer, "create_session") as span:
            span.set_attribute("user_id", user_id)
            span.set_attribute("device_id", device_id)
            span.set_attribute("ip_address", ip_address)

            # Validate token
            validation = await self.auth_client.validate_token(token)

            if not validation.get('valid', False):
                logger.warning(f"Invalid token for user {user_id}")
                span.set_attribute("token_valid", False)
                return None, False

            # Make sure user in token matches provided user_id
            token_user_id = validation.get('userId')
            span.set_attribute("token_user_id", token_user_id)

            if token_user_id != user_id:
                logger.warning(f"Token user_id {token_user_id} doesn't match provided user_id {user_id}")
                span.set_attribute("user_id_match", False)
                span.set_attribute("error", "User ID mismatch")
                return None, False

            try:
                # Check for existing sessions for this user
                active_sessions = await self.db_manager.get_active_user_sessions(user_id)
                
                # If user already has active sessions, end them
                for session in active_sessions:
                    await self.db_manager.end_session(session.session_id)
                    logger.info(f"Ended previous session {session.session_id} for user {user_id}")
                    
                    # If there was a simulator running, stop it
                    if hasattr(session.metadata, 'simulator_id') and session.metadata.simulator_id:
                        await self.stop_simulator(session.session_id, token, force=True)
                
                # Create new session
                session_id, is_new = await self.db_manager.create_session(user_id, ip_address)

                # Set additional metadata including device_id
                await self.db_manager.update_session_metadata(session_id, {
                    'pod_name': self.pod_name,
                    'ip_address': ip_address,
                    'device_id': device_id
                })

                # Track session creation
                track_session_operation("create")

                # Publish session creation event if Redis is available
                if self.redis:
                    await self.redis.publish('session_events', json.dumps({
                        'type': 'session_created',
                        'session_id': session_id,
                        'user_id': user_id,
                        'device_id': device_id,
                        'pod_name': self.pod_name,
                        'timestamp': time.time()
                    }))

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
        
    async def update_session_activity(self, session_id: str) -> bool:
        """
        Update the session activity timestamp
        
        Args:
            session_id: The session ID
        
        Returns:
            Success status
        """
        try:
            # Update session activity in database
            return await self.db_manager.update_session_activity(session_id)
        except Exception as e:
            logger.error(f"Error updating session activity: {e}")
            return False

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

                # Enhanced simulator shutdown with graceful cleanup steps
                if session.metadata.simulator_id:
                    simulator_id = session.metadata.simulator_id
                    span.set_attribute("simulator_id", simulator_id)
                    
                    # 1. First try to stop gracefully via gRPC
                    if session.metadata.simulator_endpoint:
                        try:
                            await self.exchange_client.stop_simulator(
                                session.metadata.simulator_endpoint,
                                session_id
                            )
                            logger.info(f"Successfully stopped simulator {simulator_id} via gRPC")
                        except Exception as e:
                            logger.warning(f"Failed to stop simulator via gRPC: {e}")
                    
                    # 2. Delete the K8s resources regardless of gRPC success
                    try:
                        await self.simulator_manager.k8s_client.delete_simulator_deployment(simulator_id)
                        logger.info(f"Deleted K8s resources for simulator {simulator_id}")
                    except Exception as e:
                        logger.error(f"Failed to delete simulator K8s resources: {e}")
                    
                    # 3. Update database to mark simulator as stopped
                    await self.db_manager.update_simulator_status(simulator_id, SimulatorStatus.STOPPED)
                
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

    async def start_simulator(self, session_id: str, token: str, symbols: List[str] = None) -> Tuple[Optional[str], Optional[str], str]:
        """
        Start a simulator for a session
        
        Args:
            session_id: The session ID
            token: Authentication token
            symbols: List of symbols to track
            
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
            
            # Create new simulator
            simulator, error = await self.simulator_manager.create_simulator(
                session_id, 
                user_id,
                symbols
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
        
    async def get_user_from_token(self, token: str) -> Optional[str]:
        """Extract user ID from token"""
        validation = await self.auth_client.validate_token(token)
        if validation.get('valid', False):
            return validation.get('userId')
        return None
        
    async def get_or_create_user_session(self, user_id: str, token: str) -> Optional[str]:
        """Get user's active session or create a new one"""
        # Check for existing active session
        active_sessions = await self.db_manager.get_active_user_sessions(user_id)
        
        # Return first active session if exists
        if active_sessions:
            return active_sessions[0].session_id
            
        # Create new session
        session_id, _ = await self.create_session(user_id, token)
        return session_id

    async def stop_simulator(self, session_id: str, token: str = None, force: bool = False) -> Tuple[bool, str]:
        """
        Stop the simulator for a session
        
        Args:
            session_id: The session ID
            token: Authentication token (optional if force=True)
            force: Force stop without token validation
            
        Returns:
            Tuple of (success, error_message)
        """
        with optional_trace_span(self.tracer, "stop_simulator") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("force", force)
            
            # Validate session if not forcing
            user_id = None
            if not force:
                if not token:
                    span.set_attribute("error", "Missing token")
                    return False, "Missing authentication token"
                    
                user_id = await self.validate_session(session_id, token)
                if not user_id:
                    span.set_attribute("error", "Invalid session")
                    return False, "Invalid session or token"
            
            try:
                # Get session
                session = await self.db_manager.get_session(session_id)
                
                if not session:
                    span.set_attribute("error", "Session not found")
                    return False, "Session not found"
                
                # If forcing, get user_id from session
                if force and not user_id:
                    user_id = session.user_id
                    span.set_attribute("user_id", user_id)
                
                # Check if there's an active simulator
                simulator_id = session.metadata.simulator_id if hasattr(session.metadata, 'simulator_id') else None
                
                if not simulator_id:
                    span.set_attribute("error", "No active simulator")
                    return False, "No active simulator for this session"
                
                # Stop simulator
                success, error = await self.simulator_manager.stop_simulator(simulator_id)
                
                if not success and not force:
                    span.set_attribute("error", error)
                    return False, error
                
                # Update session metadata
                await self.db_manager.update_session_metadata(session_id, {
                    'simulator_status': SimulatorStatus.STOPPED.value,
                    'simulator_id': None  # Clear simulator ID
                })
                
                # Publish simulator stopped event if Redis is available
                if self.redis:
                    await self.redis.publish('session_events', json.dumps({
                        'type': 'simulator_stopped',
                        'session_id': session_id,
                        'simulator_id': simulator_id,
                        'pod_name': self.pod_name,
                        'timestamp': time.time(),
                        'forced': force
                    }))
                
                return True, ""
            except Exception as e:
                logger.error(f"Error stopping simulator: {e}")
                span.record_exception(e)
                return False, str(e)
        
    async def reconnect_session(self, session_id: str, token: str, device_id: str, attempt: int = 1) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Reconnect to a session, potentially restarting a simulator
        
        Args:
            session_id: The session ID
            token: Authentication token
            device_id: Device ID
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
            
            # Verify device_id matches
            if session.metadata.device_id != device_id:
                return None, "Device ID mismatch"
            
            # Check if simulator needs restart
            simulator_needs_restart = False
            
            if session.metadata.simulator_id:
                # Check simulator status
                status = await self.simulator_manager.get_simulator_status(session.metadata.simulator_id)
                
                if status['status'] not in ['RUNNING', 'STARTING']:
                    simulator_needs_restart = True
            
            # Update session metadata
            await self.db_manager.update_session_metadata(session_id, {
                'reconnect_count': session.metadata.reconnect_count + 1,
                'last_reconnect': time.time()
            })
            
            # Get updated session
            session = await self.db_manager.get_session(session_id)
            
            # Return session data with simulator_needs_restart flag
            session_dict = session.to_dict()
            session_dict['simulator_needs_restart'] = simulator_needs_restart
            
            return session_dict, ""
        except Exception as e:
            logger.error(f"Error reconnecting session: {e}")
            return None, str(e)