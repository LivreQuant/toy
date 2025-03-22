# interface/session-manager-service/source/main.py
import uuid
import time
import grpc
import json
import os
import socket
import threading
import logging
import signal
import sys
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
        
        # Track active connections for graceful shutdown
        self.active_connections = {}  # session_id -> list of connections
        self.active_streams = {}      # session_id -> list of stream contexts
        self.shutdown_in_progress = False
        
        # Initialize managers
        self.exchange_manager = ExchangeManager(self)
        self.frontend_manager = FrontendManager(self)
        
        # Start background cleaner for expired sessions
        self.cleaner = threading.Thread(target=self._clean_expired_sessions, daemon=True)
        self.cleaner.start()
        
        # Start health server
        start_health_server()
        
        # Set up signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        logger.info("Session manager service initialized")
    
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown"""
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)
    
    def _handle_shutdown_signal(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        self.shutdown_in_progress = True
        
        # Create a thread to handle shutdown so we don't block the signal handler
        threading.Thread(target=self._perform_graceful_shutdown, daemon=True).start()
    
    def _perform_graceful_shutdown(self):
        """Perform graceful shutdown steps"""
        try:
            logger.info("Starting graceful shutdown procedure")
            
            # 1. Notify all active connections that we're shutting down
            for session_id, connections in self.active_connections.items():
                logger.info(f"Notifying {len(connections)} connections for session {session_id} of shutdown")
                for conn in connections:
                    try:
                        if hasattr(conn, 'context') and conn.context:
                            conn.context.abort(grpc.StatusCode.UNAVAILABLE, "Service shutting down for maintenance")
                    except Exception as e:
                        logger.error(f"Error notifying connection of shutdown: {e}")
            
            # 2. Notify all active streams
            for session_id, streams in self.active_streams.items():
                logger.info(f"Notifying {len(streams)} streams for session {session_id} of shutdown")
                for stream_context in streams:
                    try:
                        if stream_context.is_active():
                            stream_context.abort(grpc.StatusCode.UNAVAILABLE, "Service shutting down for maintenance")
                    except Exception as e:
                        logger.error(f"Error notifying stream of shutdown: {e}")
            
            # 3. Wait a moment for clients to receive shutdown notice
            logger.info("Waiting for clients to process shutdown notifications")
            time.sleep(2)
            
            # 4. Close database connections
            logger.info("Closing database connections")
            self.db.close()
            
            # 5. Exit the process
            logger.info("Shutdown complete, exiting process")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")
            sys.exit(1)
    
    # Session management methods
    def CreateSession(self, request, context):
        # If shutdown is in progress, reject new sessions
        if self.shutdown_in_progress:
            context.abort(grpc.StatusCode.UNAVAILABLE, "Service is shutting down")
            return
            
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
            
            # Track this connection
            self._track_connection(existing_session_id, context)
            
            return session_manager_pb2.CreateSessionResponse(
                success=True,
                session_id=existing_session_id,
                pod_name=self.pod_name
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
            
            # Track this connection
            self._track_connection(session_id, context)
            
            # Don't start exchange service immediately - wait until needed
            
            return session_manager_pb2.CreateSessionResponse(
                success=True,
                session_id=session_id,
                pod_name=self.pod_name
            )
        else:
            return session_manager_pb2.CreateSessionResponse(
                success=False,
                error_message="Failed to create session in database"
            )
    
    def GetSession(self, request, context):
        # If shutdown is in progress, report as inactive
        if self.shutdown_in_progress:
            return session_manager_pb2.GetSessionResponse(
                session_active=False,
                error_message="Service is shutting down"
            )
            
        response = self.frontend_manager.get_session(request, context)
        
        # Track this connection
        if response.session_active:
            self._track_connection(request.session_id, context)
            
        return response
    
    def EndSession(self, request, context):
        return self.frontend_manager.end_session(request, context)
    
    def KeepAlive(self, request, context):
        # If shutdown is in progress, return failure
        if self.shutdown_in_progress:
            return session_manager_pb2.KeepAliveResponse(success=False)
            
        response = self.frontend_manager.keep_alive(request, context)
        
        # Track this connection
        if response.success:
            self._track_connection(request.session_id, context)
            
        return response
    
    def GetSessionState(self, request, context):
        # If shutdown is in progress, return error
        if self.shutdown_in_progress:
            return session_manager_pb2.GetSessionStateResponse(
                success=False,
                error_message="Service is shutting down"
            )
            
        response = self.frontend_manager.get_session_state(request, context)
        
        # Track this connection
        if response.success:
            self._track_connection(request.session_id, context)
            
        # Add pod name to response
        if hasattr(response, 'pod_name'):
            response.pod_name = self.pod_name
            
        return response
    
    def ReconnectSession(self, request, context):
        # If shutdown is in progress, reject reconnections
        if self.shutdown_in_progress:
            return session_manager_pb2.ReconnectSessionResponse(
                success=False,
                error_message="Service is shutting down"
            )
            
        response = self.frontend_manager.reconnect_session(request, context)
        
        # Track this connection
        if response.success:
            self._track_connection(response.session_id, context)
            
        # Add pod name to response
        if hasattr(response, 'pod_name'):
            response.pod_name = self.pod_name
        else:
            # If pod_name field doesn't exist in proto, we can't add it directly
            # You might need to update your proto definition
            pass
            
        return response
    
    def UpdateConnectionQuality(self, request, context):
        # If shutdown is in progress, recommend reconnect
        if self.shutdown_in_progress:
            return session_manager_pb2.ConnectionQualityResponse(
                quality="poor",
                reconnect_recommended=True
            )
            
        response = self.frontend_manager.update_connection_quality(request, context)
        
        # Track this connection
        self._track_connection(request.session_id, context)
            
        return response
    
    def StreamExchangeData(self, request, context):
        """Stream exchange data to frontend client with connection limits"""
        # If shutdown is in progress, reject new streams
        if self.shutdown_in_progress:
            context.abort(grpc.StatusCode.UNAVAILABLE, "Service is shutting down")
            return
            
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
        
        # Track this stream
        self._track_stream(session_id, context)
        
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
            
            # Untrack this stream
            self._untrack_stream(session_id, context)
    
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
        while not self.shutdown_in_progress:
            try:
                time.sleep(300)  # Run every 5 minutes
                
                # Skip cleanup if shutdown is in progress
                if self.shutdown_in_progress:
                    break
                    
                logger.info("Running session cleanup task")
                
                # Use database function for cleanup
                self.db.cleanup_expired_sessions()
                
                logger.info("Session cleanup completed")
            except Exception as e:
                logger.error(f"Error in session cleanup task: {e}")
    
    # Connection tracking for graceful shutdown
    def _track_connection(self, session_id, context):
        """Track connection for graceful shutdown"""
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        
        # Add context to list of active connections
        self.active_connections[session_id].append({
            'context': context,
            'timestamp': datetime.now(timezone.utc)
        })
        
        # Set up callback for when connection is terminated
        context.add_callback(lambda: self._connection_terminated(session_id, context))
    
    def _connection_terminated(self, session_id, context):
        """Handle connection termination"""
        if session_id in self.active_connections:
            # Remove this connection from tracking
            self.active_connections[session_id] = [
                conn for conn in self.active_connections[session_id]
                if conn.get('context') != context
            ]
    
    def _track_stream(self, session_id, context):
        """Track stream for graceful shutdown"""
        if session_id not in self.active_streams:
            self.active_streams[session_id] = []
        
        # Add context to list of active streams
        self.active_streams[session_id].append(context)
        
        # Set up callback for when stream is terminated
        context.add_callback(lambda: self._stream_terminated(session_id, context))
    
    def _untrack_stream(self, session_id, context):
        """Untrack stream explicitly"""
        if session_id in self.active_streams:
            self.active_streams[session_id] = [
                stream for stream in self.active_streams[session_id]
                if stream != context
            ]
    
    def _stream_terminated(self, session_id, context):
        """Handle stream termination"""
        self._untrack_stream(session_id, context)

def serve():
    # Create auth channel with TLS
    auth_channel = create_auth_channel()
    
    # Load server credentials for this service
    server_key = open('certs/server.key', 'rb').read()
    server_cert = open('certs/server.crt', 'rb').read()
    ca_cert = open('certs/ca.crt', 'rb').read()
    
        # Create server credentials
    server_credentials = grpc.ssl_server_credentials(
        [(server_key, server_cert)],
        root_certificates=ca_cert,
        require_client_auth=True  # Require mutual TLS
    )
    
    # Create gRPC server
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        options=[
            ('grpc.max_receive_message_length', 10 * 1024 * 1024),  # 10 MB
            ('grpc.max_send_message_length', 10 * 1024 * 1024),     # 10 MB
            ('grpc.keepalive_time_ms', 10000),                      # 10 seconds
            ('grpc.keepalive_timeout_ms', 5000),                    # 5 seconds
            ('grpc.keepalive_permit_without_calls', 1),             # Allow keepalive without active calls
            ('grpc.http2.max_pings_without_data', 0),               # Allow unlimited pings without data
            ('grpc.http2.min_time_between_pings_ms', 10000),        # Minimum time between pings
            ('grpc.http2.min_ping_interval_without_data_ms', 5000), # Minimum ping interval without data
            ('grpc.max_connection_idle_ms', 60000),                 # Maximum idle time before ping
            ('grpc.max_connection_age_ms', 300000),                 # Maximum connection age
            ('grpc.max_connection_age_grace_ms', 10000)             # Grace period for old connections
        ]
    )
    
    # Add service to server
    servicer = SessionManagerServicer(auth_channel)
    session_manager_pb2_grpc.add_SessionManagerServiceServicer_to_server(
        servicer, server
    )
    
    # Start server with TLS
    service_port = int(os.getenv('SERVICE_PORT', '50052'))
    server.add_secure_port(f'[::]:{service_port}', server_credentials)
    server.start()
    
    logger.info(f"Session Manager Service started with TLS on port {service_port}")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, initiating shutdown")
        servicer._handle_shutdown_signal(signal.SIGINT, None)
        time.sleep(5)

if __name__ == '__main__':
    serve()