import logging
import time
import uuid
import json
from typing import Dict, Optional, List

logger = logging.getLogger('session_manager')

class SessionManager:
    """Manages session lifecycle and state"""
    
    def __init__(self, db_manager, auth_client, exchange_client, pod_name=None):
        self.db = db_manager
        self.auth_client = auth_client
        self.exchange_client = exchange_client
        self.pod_name = pod_name
        
        # Active sessions
        self.active_sessions = {}  # session_id -> session_info
        
        # Session settings
        self.session_timeout = 3600  # 1 hour
        self.extension_threshold = 1800  # 30 minutes
        
        # Start cleanup task
        self.start_cleanup_task()
    
    async def start_cleanup_task(self):
        """Start periodic cleanup of expired sessions"""
        while True:
            await asyncio.sleep(300)  # Check every 5 minutes
            await self.cleanup_expired_sessions()
    
    async def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        try:
            logger.info("Running session cleanup task")
            await self.db.cleanup_expired_sessions()
        except Exception as e:
            logger.error(f"Error in session cleanup: {e}")
    
    async def create_session(self, user_id, token, client_ip=None):
        """Create a new session or return existing one"""
        # Check for existing session
        existing_session_id = await self.db.get_user_session(user_id)
        if existing_session_id:
            # Update existing session
            await self.db.update_session_activity(existing_session_id)
            await self.db.update_session_metadata(existing_session_id, {
                "session_host": self.pod_name,
                "last_connected_ip": client_ip
            })
            
            logger.info(f"User {user_id} reconnected to existing session {existing_session_id}")
            return existing_session_id, False
        
        # Create a new session
        session_id = str(uuid.uuid4())
        success = await self.db.create_session(session_id, user_id, client_ip)
        
        if success:
            # Add metadata
            await self.db.update_session_metadata(session_id, {
                "session_host": self.pod_name,
                "created_at": time.time(),
                "frontend_connections": 0,
                "simulator_id": None,
                "simulator_endpoint": None
            })
            
            logger.info(f"Created new session {session_id} for user {user_id}")
            return session_id, True
        
        return None, False
    
    async def validate_session(self, session_id, token):
        """Validate session and token"""
        # Validate token
        validate_result = await self.auth_client.validate_token(token)
        if not validate_result['valid']:
            return None
        
        user_id = validate_result['user_id']
        
        # Get session
        session = await self.db.get_session(session_id)
        if not session:
            return None
        
        # Check if session belongs to user
        if str(session['user_id']) != user_id:
            return None
        
        # Check if session is expired
        if session.get('expires_at') and session['expires_at'] < time.time():
            return None
        
        # Update session activity
        await self.db.update_session_activity(session_id)
        
        return user_id
    
    async def get_session(self, session_id):
        """Get session data"""
        return await self.db.get_session(session_id)
    
    async def end_session(self, session_id, token):
        """End a session"""
        # Validate session and token
        user_id = await self.validate_session(session_id, token)
        if not user_id:
            return False, "Invalid session or token"
        
        # Get simulator ID
        session = await self.db.get_session(session_id)
        simulator_id = session.get('simulator_id')
        
        # Stop simulator if running
        if simulator_id:
            try:
                await self.exchange_client.stop_simulator(simulator_id)
            except Exception as e:
                logger.error(f"Error stopping simulator {simulator_id}: {e}")
        
        # Delete session
        success = await self.db.end_session(session_id)
        
        if success:
            logger.info(f"Ended session {session_id} for user {user_id}")
            return True, ""
        
        return False, "Failed to end session"
    
    async def start_simulator(self, session_id, token):
        """Start a simulator for a session"""
        # Validate session and token
        user_id = await self.validate_session(session_id, token)
        if not user_id:
            return None, None, "Invalid session or token"
        
        # Check if simulator already running
        session = await self.db.get_session(session_id)
        if session.get('simulator_id'):
            # Check if simulator is still active
            simulator_id = session['simulator_id']
            simulator_status = await self.exchange_client.get_simulator_status(simulator_id)
            
            if simulator_status == 'RUNNING':
                logger.info(f"Simulator {simulator_id} already running for session {session_id}")
                return simulator_id, session.get('simulator_endpoint'), ""
        
        # Start new simulator
        try:
            result = await self.exchange_client.start_simulator(session_id, user_id)
            if result['success']:
                simulator_id = result['simulator_id']
                simulator_endpoint = result['simulator_endpoint']
                
                # Update session
                await self.db.update_session_metadata(session_id, {
                    "simulator_id": simulator_id,
                    "simulator_endpoint": simulator_endpoint,
                    "simulator_status": "STARTING"
                })
                
                # Register exchange service
                await self.db.register_exchange_service(
                    session_id=session_id,
                    exchange_id=simulator_id,
                    endpoint=simulator_endpoint
                )
                
                logger.info(f"Started simulator {simulator_id} for session {session_id}")
                return simulator_id, simulator_endpoint, ""
            else:
                return None, None, result.get('error_message', "Failed to start simulator")
        except Exception as e:
            logger.error(f"Error starting simulator: {e}")
            return None, None, str(e)
    
    async def stop_simulator(self, session_id, token):
        """Stop a simulator for a session"""
        # Validate session and token
        user_id = await self.validate_session(session_id, token)
        if not user_id:
            return False, "Invalid session or token"
        
        # Get simulator ID
        session = await self.db.get_session(session_id)
        simulator_id = session.get('simulator_id')
        
        if not simulator_id:
            return False, "No active simulator for this session"
        
        # Stop simulator
        try:
            result = await self.exchange_client.stop_simulator(simulator_id)
            if result['success']:
                # Update session
                await self.db.update_session_metadata(session_id, {
                    "simulator_id": None,
                    "simulator_endpoint": None,
                    "simulator_status": "STOPPED"
                })
                
                # Deregister exchange service
                await self.db.deactivate_exchange_service(simulator_id)
                
                logger.info(f"Stopped simulator {simulator_id} for session {session_id}")
                return True, ""
            else:
                return False, result.get('error_message', "Failed to stop simulator")
        except Exception as e:
            logger.error(f"Error stopping simulator: {e}")
            return False, str(e)
    
    async def get_simulator_status(self, session_id, token):
        """Get status of a simulator for a session"""
        # Validate session and token
        user_id = await self.validate_session(session_id, token)
        if not user_id:
            return None, "Invalid session or token"
        
        # Get simulator ID
        session = await self.db.get_session(session_id)
        simulator_id = session.get('simulator_id')
        
        if not simulator_id:
            return {"status": "NONE"}, ""
        
        # Get simulator status
        try:
            status = await self.exchange_client.get_simulator_status(simulator_id)
            return {"status": status, "simulator_id": simulator_id}, ""
        except Exception as e:
            logger.error(f"Error getting simulator status: {e}")
            return None, str(e)
    
    async def update_connection_quality(self, session_id, token, data):
        """Update connection quality metrics"""
        # Validate session
        user_id = await self.validate_session(session_id, token)
        if not user_id:
            return "poor", True
        
        # Determine connection quality
        latency_ms = data.get('latency_ms', 0)
        missed_heartbeats = data.get('missed_heartbeats', 0)
        
        quality = "good"
        reconnect_recommended = False
        
        if missed_heartbeats >= 3:
            quality = "poor"
            reconnect_recommended = True
        elif missed_heartbeats > 0 or latency_ms > 500:
            quality = "degraded"
            reconnect_recommended = missed_heartbeats >= 2
        
        # Store metrics
        await self.db.update_session_metadata(session_id, {
            "connection_quality": {
                "latency_ms": latency_ms,
                "missed_heartbeats": missed_heartbeats,
                "connection_type": data.get('connection_type', 'unknown'),
                "quality": quality,
                "timestamp": time.time()
            }
        })
        
        return quality, reconnect_recommended
    
    async def reconnect_session(self, session_id, token, attempt=1):
        """Handle session reconnection"""
        # Validate token 
        user_id = await self.auth_client.validate_token(token)['user_id']
        if not user_id:
            return None, "Invalid token"
        
        # Get session
        session = await self.db.get_session(session_id)
        
        if not session:
            # Create a new session
            new_session_id = str(uuid.uuid4())
            await self.db.create_session(new_session_id, user_id)
            await self.db.update_session_metadata(new_session_id, {
                "session_host": self.pod_name,
                "created_at": time.time(),
                "reconnect_from": session_id
            })
            
            return {
                "success": True,
                "session_id": new_session_id,
                "simulator_id": None,
                "simulator_status": "NONE",
                "new_session": True
            }, ""
        
        # Check if session belongs to user
        if str(session['user_id']) != str(user_id):
            return None, "Session does not belong to user"
        
        # Check pod transfer
        previous_pod = session.get('session_host')
        pod_transferred = previous_pod and previous_pod != self.pod_name
        
        # Update session
        await self.db.update_session_activity(session_id)
        await self.db.update_session_metadata(session_id, {
            "session_host": self.pod_name,
            "last_reconnect": time.time(),
            "reconnect_attempt": attempt
        })
        
        simulator_id = session.get('simulator_id')
        simulator_status = "UNKNOWN"
        
        if simulator_id:
            try:
                simulator_status = await self.exchange_client.get_simulator_status(simulator_id)
            except:
                simulator_status = "UNKNOWN"
        
        return {
            "success": True,
            "session_id": session_id,
            "simulator_id": simulator_id,
            "simulator_endpoint": session.get('simulator_endpoint'),
            "simulator_status": simulator_status,
            "pod_transferred": pod_transferred,
            "new_session": False
        }, ""