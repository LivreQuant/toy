# main.py
import uuid
import time
import grpc
import json
import os
import socket
import threading
import logging
from concurrent import futures
from datetime import datetime, timezone

# Import protocol buffers
import session_manager_pb2
import session_manager_pb2_grpc
import auth_pb2
import auth_pb2_grpc

# Import our managers
from db_manager import DatabaseManager
from frontend_manager import FrontendManager
from exchange_manager import ExchangeManager
from health_server import start_health_server

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('session_manager')

class SessionManagerServicer(session_manager_pb2_grpc.SessionManagerServiceServicer):
    def __init__(self, auth_channel):
        # Store pod identifier
        self.pod_name = os.getenv('POD_NAME', socket.gethostname())
        logger.info(f"Initializing session manager on pod {self.pod_name}")
        
        # Create auth stub
        self.auth_stub = auth_pb2_grpc.AuthServiceStub(auth_channel)
        
        # Create database manager
        self.db = DatabaseManager()
        
        # Configuration
        self.session_timeout = int(os.getenv('SESSION_TIMEOUT_SECONDS', '3600'))  # 1 hour
        self.session_extension_threshold = int(os.getenv('SESSION_EXTENSION_THRESHOLD', '1800'))  # 30 minutes
        self.simulator_timeout = int(os.getenv('SIMULATOR_TIMEOUT_SECONDS', '600'))  # 10 minutes
        self.max_frontend_connections = int(os.getenv('MAX_FRONTEND_CONNECTIONS', '3'))
        
        # Initialize managers
        self.exchange_manager = ExchangeManager(self)
        self.frontend_manager = FrontendManager(self)
        
        # Start background cleaner for expired sessions
        self.cleaner = threading.Thread(target=self._clean_expired_sessions, daemon=True)
        self.cleaner.start()
        
        # Start health server
        start_health_server()
        
        logger.info("Session manager service initialized")
    
    # Session management methods
    def CreateSession(self, request, context):
        # Validate token
        user_id = self.validate_token(request.token)
        if not user_id:
            return session_manager_pb2.CreateSessionResponse(
                success=False,
                error_message="Invalid authentication token"
            )
        
        # Check if user already has an active session
        existing_session_id = self.db.get_user_session(user_id)
        if existing_session_id:
            # Session exists, update activity
            self.db.update_session_activity(existing_session_id)
            logger.info(f"User {user_id} has existing session {existing_session_id}")
            
            # Update pod hosting info
            self.db.update_session_metadata(existing_session_id, {
                "session_host": self.pod_name
            })
            
            return session_manager_pb2.CreateSessionResponse(
                success=True,
                session_id=existing_session_id
            )
        
        # Create new session
        session_id = str(uuid.uuid4())
        
        # Get client IP from context if available
        client_ip = context.peer() if hasattr(context, 'peer') else 'unknown'
        
        # Create session in database
        success = self.db.create_session(session_id, user_id, client_ip)
        
        if success:
            # Add pod hosting info
            self.db.update_session_metadata(session_id, {
                "session_host": self.pod_name
            })
            
            logger.info(f"Created new session {session_id} for user {user_id} on pod {self.pod_name}")
            
            # Don't start exchange service immediately - wait until needed
            
            return session_manager_pb2.CreateSessionResponse(
                success=True,
                session_id=session_id
            )
        else:
            return session_manager_pb2.CreateSessionResponse(
                success=False,
                error_message="Failed to create session in database"
            )
    
    def GetSession(self, request, context):
        return self.frontend_manager.get_session(request, context)
    
    def EndSession(self, request, context):
        return self.frontend_manager.end_session(request, context)
    
    def KeepAlive(self, request, context):
        return self.frontend_manager.keep_alive(request, context)
    
    def GetSessionState(self, request, context):
        return self.frontend_manager.get_session_state(request, context)
    
    def ReconnectSession(self, request, context):
        return self.frontend_manager.reconnect_session(request, context)
    
    def UpdateConnectionQuality(self, request, context):
        return self.frontend_manager.update_connection_quality(request, context)
    
    def StreamExchangeData(self, request, context):
        """Stream exchange data to frontend client with connection limits"""
        session_id = request.session_id
        token = request.token
        
        # Validate token and session
        user_id = self.validate_session_access(token, session_id)
        if not user_id:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid token or session")
            return
        
        # Update session activity
        self.db.update_session_activity(session_id)
        
        # Check connection limit
        session_data = self.db.get_session(session_id)
        frontend_connections = session_data.get('frontend_connections', 0)
        
        if frontend_connections >= self.max_frontend_connections:
            context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, 
                        f"Maximum frontend connections ({self.max_frontend_connections}) reached for this session")
            return
        
        # Increment connection count
        self.db.update_session_metadata(session_id, {
            'frontend_connections': frontend_connections + 1
        })
        
        # Ensure exchange service is activated
        exchange_id, exchange_endpoint = self.exchange_manager.activate_session(session_id, user_id)
        if not exchange_id or not exchange_endpoint:
            context.abort(grpc.StatusCode.INTERNAL, "Failed to activate exchange service")
            return
            
        try:
            # Stream exchange data
            self.exchange_manager.stream_exchange_data(session_id, user_id, request, context)
        finally:
            # Decrement connection count when done
            current_data = self.db.get_session(session_id)
            if current_data:
                self.db.update_session_metadata(session_id, {
                    'frontend_connections': max(0, current_data.get('frontend_connections', 1) - 1)
                })
    
    # Authentication methods
    def validate_token(self, token):
        """Validate token and return user_id if valid"""
        try:
            validate_response = self.auth_stub.ValidateToken(
                auth_pb2.ValidateTokenRequest(token=token)
            )
            
            if not validate_response.valid:
                return None
            
            return validate_response.user_id
        except Exception as e:
            logger.error(f"Error validating token: {e}")
            return None
    
    def validate_session_access(self, token, session_id):
        """Validate token and session access rights"""
        user_id = self.validate_token(token)
        if not user_id:
            return None
        
        # Get session from database
        session = self.db.get_session(session_id)
        if not session:
            return None
        
        # Check user ownership
        if str(session.get('user_id')) != user_id:
            return None
        
        # Check expiration
        if 'expires_at' in session and session['expires_at'] < time.time():
            return None
        
        return user_id
    
    def get_session_data(self, session_id):
        """Get session data from database"""
        return self.db.get_session(session_id)
    
    def update_session_metadata(self, session_id, updates):
        """Update session metadata"""
        return self.db.update_session_metadata(session_id, updates)
    
    # Cleanup methods
    def _clean_expired_sessions(self):
        """Background task to clean expired sessions"""
        while True:
            try:
                time.sleep(300)  # Run every 5 minutes
                logger.info("Running session cleanup task")
                
                # Use database function for cleanup
                self.db.cleanup_expired_sessions()
                
                logger.info("Session cleanup completed")
            except Exception as e:
                logger.error(f"Error in session cleanup task: {e}")


def serve():
    # Get environment configuration
    auth_service = os.getenv('AUTH_SERVICE', 'auth-service:50051')
    service_port = int(os.getenv('SERVICE_PORT', '50052'))
    
    # Create auth channel with retry options
    channel_options = [
        ('grpc.enable_retries', 1),
        ('grpc.service_config', json.dumps({
            'methodConfig': [{
                'name': [{}],  # Apply to all methods
                'retryPolicy': {
                    'maxAttempts': 5,
                    'initialBackoff': '0.1s',
                    'maxBackoff': '10s',
                    'backoffMultiplier': 2.0,
                    'retryableStatusCodes': ['UNAVAILABLE']
                }
            }]
        }))
    ]
    auth_channel = grpc.insecure_channel(auth_service, options=channel_options)
    
    # Create gRPC server
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        options=[
            ('grpc.max_receive_message_length', 10 * 1024 * 1024),  # 10 MB
            ('grpc.max_send_message_length', 10 * 1024 * 1024),     # 10 MB
            ('grpc.keepalive_time_ms', 10000),                      # 10 seconds
            ('grpc.keepalive_timeout_ms', 5000),                    # 5 seconds
            ('grpc.keepalive_permit_without_calls', 1),             # Allow keepalive without active calls
        ]
    )
    
    # Add service to server
    session_manager_pb2_grpc.add_SessionManagerServiceServicer_to_server(
        SessionManagerServicer(auth_channel), server
    )
    
    # Start server
    server.add_insecure_port(f'[::]:{service_port}')
    server.start()
    logger.info(f"Session Manager Service started on port {service_port}")
    
    # Wait for termination
    server.wait_for_termination()


if __name__ == '__main__':
    serve()