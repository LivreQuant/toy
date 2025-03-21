# session_manager.py
import uuid
import time
import grpc
import json
from concurrent import futures
import logging
import session_manager_pb2
import session_manager_pb2_grpc
import auth_pb2
import auth_pb2_grpc
from redis import Redis

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('session_manager')

class SessionManagerServicer(session_manager_pb2_grpc.SessionManagerServiceServicer):
    def __init__(self, auth_channel, redis_client):
        self.auth_stub = auth_pb2_grpc.AuthServiceStub(auth_channel)
        self.redis = redis_client
        # Session timeout - 1 hour by default
        self.session_timeout = 3600
        # Time after which we extend the session TTL - 30 minutes
        self.session_extension_threshold = 1800
        # Maximum time to keep a simulator reserved after last activity - 10 minutes
        self.simulator_timeout = 600
        
        # Start background cleaner for expired sessions
        import threading
        self.cleaner = threading.Thread(target=self._clean_expired_sessions, daemon=True)
        self.cleaner.start()
    
    def CreateSession(self, request, context):
        # Validate token
        validate_response = self.auth_stub.ValidateToken(
            auth_pb2.ValidateTokenRequest(token=request.token)
        )
        
        if not validate_response.valid:
            logger.warning(f"Invalid token during CreateSession")
            return session_manager_pb2.CreateSessionResponse(
                success=False,
                error_message="Invalid authentication token"
            )
        
        user_id = validate_response.user_id
        
        # Check if user already has an active session
        existing_session_key = f"user:{user_id}:active_session"
        existing_session_id = self.redis.get(existing_session_key)
        
        if existing_session_id:
            # Check if existing session is still valid
            session_data = self._get_session_data(existing_session_id.decode())
            if session_data and (time.time() - session_data.get('last_active', 0)) < self.session_timeout:
                logger.info(f"User {user_id} has existing session {existing_session_id.decode()}")
                # Return existing session
                return session_manager_pb2.CreateSessionResponse(
                    success=True,
                    session_id=existing_session_id.decode()
                )
        
        # Create new session
        session_id = str(uuid.uuid4())
        logger.info(f"Creating new session {session_id} for user {user_id}")
        
        session_data = {
            "user_id": user_id,
            "created_at": time.time(),
            "last_active": time.time(),
            "simulator_endpoint": None,
            "simulator_id": None
        }
        
        # Store session data in Redis
        self._save_session_data(session_id, session_data)
        
        # Map user to session
        self.redis.set(f"user:{user_id}:active_session", session_id)
        self.redis.expire(f"user:{user_id}:active_session", self.session_timeout)
        
        return session_manager_pb2.CreateSessionResponse(
            success=True,
            session_id=session_id
        )
    
    def GetSession(self, request, context):
        session_id = request.session_id
        
        # Validate token
        validate_response = self.auth_stub.ValidateToken(
            auth_pb2.ValidateTokenRequest(token=request.token)
        )
        
        if not validate_response.valid:
            logger.warning(f"Invalid token during GetSession for {session_id}")
            return session_manager_pb2.GetSessionResponse(
                session_active=False,
                error_message="Invalid authentication token"
            )
        
        user_id = validate_response.user_id
        
        # Get session data
        session_data = self._get_session_data(session_id)
        
        if not session_data:
            logger.warning(f"Session {session_id} not found")
            return session_manager_pb2.GetSessionResponse(
                session_active=False,
                error_message="Session not found"
            )
        
        # Check if session belongs to requesting user
        if session_data.get("user_id") != user_id:
            logger.warning(f"Session {session_id} does not belong to user {user_id}")
            return session_manager_pb2.GetSessionResponse(
                session_active=False,
                error_message="Session does not belong to user"
            )
        
        # Check if session has expired
        last_active = session_data.get("last_active", 0)
        if time.time() - last_active > self.session_timeout:
            # Clean up expired session
            logger.info(f"Session {session_id} has expired")
            self._delete_session(session_id, user_id)
            return session_manager_pb2.GetSessionResponse(
                session_active=False,
                error_message="Session has expired"
            )
        
        # Update last active timestamp
        self._update_session_activity(session_id, session_data)
        
        # Check if we should extend the TTL
        if time.time() - last_active > self.session_extension_threshold:
            # Extend TTL
            logger.info(f"Extending TTL for session {session_id}")
            self.redis.expire(f"session:{session_id}", self.session_timeout)
            self.redis.expire(f"user:{user_id}:active_session", self.session_timeout)
        
        return session_manager_pb2.GetSessionResponse(
            session_active=True,
            simulator_endpoint=session_data.get("simulator_endpoint") or ""
        )
    
    def EndSession(self, request, context):
        session_id = request.session_id
        
        # Validate token
        validate_response = self.auth_stub.ValidateToken(
            auth_pb2.ValidateTokenRequest(token=request.token)
        )
        
        if not validate_response.valid:
            logger.warning(f"Invalid token during EndSession for {session_id}")
            return session_manager_pb2.EndSessionResponse(
                success=False,
                error_message="Invalid authentication token"
            )
        
        user_id = validate_response.user_id
        
        # Get session data
        session_data = self._get_session_data(session_id)
        
        if not session_data:
            logger.warning(f"Session {session_id} not found during EndSession")
            return session_manager_pb2.EndSessionResponse(
                success=False,
                error_message="Session not found"
            )
        
        # Check if session belongs to requesting user
        if session_data.get("user_id") != user_id:
            logger.warning(f"Session {session_id} does not belong to user {user_id}")
            return session_manager_pb2.EndSessionResponse(
                success=False,
                error_message="Session does not belong to user"
            )
        
        # Delete session
        logger.info(f"Ending session {session_id} for user {user_id}")
        self._delete_session(session_id, user_id)
        
        return session_manager_pb2.EndSessionResponse(success=True)
    
    def KeepAlive(self, request, context):
        session_id = request.session_id
        
        # Validate token
        validate_response = self.auth_stub.ValidateToken(
            auth_pb2.ValidateTokenRequest(token=request.token)
        )
        
        if not validate_response.valid:
            logger.warning(f"Invalid token during KeepAlive for {session_id}")
            return session_manager_pb2.KeepAliveResponse(success=False)
        
        user_id = validate_response.user_id
        
        # Get session data
        session_data = self._get_session_data(session_id)
        
        if not session_data:
            logger.warning(f"Session {session_id} not found during KeepAlive")
            return session_manager_pb2.KeepAliveResponse(success=False)
        
        # Check if session belongs to requesting user
        if session_data.get("user_id") != user_id:
            logger.warning(f"Session {session_id} does not belong to user {user_id}")
            return session_manager_pb2.KeepAliveResponse(success=False)
        
        # Update last active timestamp
        self._update_session_activity(session_id, session_data)
        
        return session_manager_pb2.KeepAliveResponse(success=True)
    
    def GetSessionState(self, request, context):
        session_id = request.session_id
        
        # Validate token
        validate_response = self.auth_stub.ValidateToken(
            auth_pb2.ValidateTokenRequest(token=request.token)
        )
        
        if not validate_response.valid:
            logger.warning(f"Invalid token during GetSessionState for {session_id}")
            return session_manager_pb2.GetSessionStateResponse(
                success=False,
                error_message="Invalid authentication token"
            )
        
        user_id = validate_response.user_id
        
        # Get session data
        session_data = self._get_session_data(session_id)
        
        if not session_data:
            logger.warning(f"Session {session_id} not found during GetSessionState")
            return session_manager_pb2.GetSessionStateResponse(
                success=False,
                error_message="Session not found"
            )
        
        # Check if session belongs to requesting user
        if session_data.get("user_id") != user_id:
            logger.warning(f"Session {session_id} does not belong to user {user_id}")
            return session_manager_pb2.GetSessionStateResponse(
                success=False,
                error_message="Session does not belong to user"
            )
        
        # Update last active timestamp
        self._update_session_activity(session_id, session_data)
        
        # Return session state
        return session_manager_pb2.GetSessionStateResponse(
            success=True,
            simulator_id=session_data.get("simulator_id") or "",
            simulator_endpoint=session_data.get("simulator_endpoint") or "",
            session_created_at=int(session_data.get("created_at", 0)),
            last_active=int(session_data.get("last_active", 0))
        )
    
    def _get_session_data(self, session_id):
        data = self.redis.get(f"session:{session_id}")
        if not data:
            return None
        
        try:
            return json.loads(data.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Error decoding session data for {session_id}: {e}")
            return None
    
    def _save_session_data(self, session_id, data):
        self.redis.set(f"session:{session_id}", json.dumps(data))
        self.redis.expire(f"session:{session_id}", self.session_timeout)
    
    def _update_session_activity(self, session_id, session_data):
        session_data["last_active"] = time.time()
        self._save_session_data(session_id, session_data)
    
    def _delete_session(self, session_id, user_id):
        # Delete session data
        self.redis.delete(f"session:{session_id}")
        
        # Delete user-to-session mapping
        self.redis.delete(f"user:{user_id}:active_session")
        
        # Get simulator ID for cleanup
        simulator_id = self.redis.get(f"session:{session_id}:simulator")
        if simulator_id:
            # Mark simulator for delayed cleanup
            # This gives time for reconnection
            self.redis.set(f"simulator:{simulator_id.decode()}:pending_cleanup", time.time())
            self.redis.expire(f"simulator:{simulator_id.decode()}:pending_cleanup", self.simulator_timeout)
    
    def _clean_expired_sessions(self):
        while True:
            try:
                time.sleep(300)  # Check every 5 minutes
                logger.info("Running session cleanup task")
                
                # Clean up expired sessions
                cursor = 0
                while True:
                    cursor, keys = self.redis.scan(cursor, match="session:*", count=100)
                    
                    for key in keys:
                        try:
                            if b":simulator" in key or b":pending_cleanup" in key:
                                continue  # Skip non-session keys
                                
                            session_id = key.decode().split(":")[1]
                            session_data = self._get_session_data(session_id)
                            
                            if session_data and time.time() - session_data.get("last_active", 0) > self.session_timeout:
                                # Session expired, clean it up
                                logger.info(f"Cleaning expired session: {session_id}")
                                self._delete_session(session_id, session_data.get("user_id"))
                        except Exception as e:
                            logger.error(f"Error processing session key {key}: {e}")
                    
                    if cursor == 0:
                        break
                
                # Clean up pending simulator cleanups
                cursor = 0
                while True:
                    cursor, keys = self.redis.scan(cursor, match="simulator:*:pending_cleanup", count=100)
                    
                    for key in keys:
                        try:
                            simulator_id = key.decode().split(":")[1]
                            pending_since = float(self.redis.get(key).decode())
                            
                            if time.time() - pending_since > self.simulator_timeout:
                                # Simulator hasn't been reclaimed, clean it up
                                logger.info(f"Cleaning up simulator: {simulator_id}")
                                # In production: call simulator manager to stop the simulator
                                self.redis.delete(key)
                        except Exception as e:
                            logger.error(f"Error processing simulator cleanup key {key}: {e}")
                    
                    if cursor == 0:
                        break
                
            except Exception as e:
                logger.error(f"Error in session cleanup task: {e}")

def serve():
    auth_channel = grpc.insecure_channel('auth:50051')
    redis_client = Redis(host='redis', port=6379, db=0)
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    session_manager_pb2_grpc.add_SessionManagerServiceServicer_to_server(
        SessionManagerServicer(auth_channel, redis_client), server
    )
    server.add_insecure_port('[::]:50052')
    server.start()
    logger.info("Session Manager Service started on port 50052")
    server.wait_for_termination()

if __name__ == '__main__