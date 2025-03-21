# frontend_manager.py
import logging
import time
import uuid

import session_manager_pb2

logger = logging.getLogger('frontend_manager')

class FrontendManager:
    """Manages frontend connections and session operations"""
    
    def __init__(self, session_service):
        self.session_service = session_service
        self.db = session_service.db
        
        # Get source IP header from environment
        self.source_ip_header = 'x-forwarded-for'  # EKS/ALB uses this by default
    
    def get_client_ip(self, context):
        """Extract client IP from gRPC context metadata"""
        metadata = dict(context.invocation_metadata())
        if self.source_ip_header in metadata:
            # Extract the first IP if there are multiple in the header
            return metadata[self.source_ip_header].split(',')[0].strip()
        return context.peer()
    
    def get_session(self, request, context):
        session_id = request.session_id
        token = request.token
        
        # Validate token and session access
        user_id = self.session_service.validate_session_access(token, session_id)
        if not user_id:
            logger.warning(f"Invalid session access in GetSession for {session_id}")
            return session_manager_pb2.GetSessionResponse(
                session_active=False,
                error_message="Invalid session or authentication"
            )
        
        # Update session activity
        self.db.update_session_activity(session_id)
        
        # Get session data
        session_data = self.session_service.get_session_data(session_id)
        
        # Get simulator endpoint
        simulator_endpoint = session_data.get("simulator_endpoint", "")
        
        # Log client information
        client_ip = self.get_client_ip(context)
        logger.info(f"Session {session_id} accessed from {client_ip} via pod {self.session_service.pod_name}")
        
        return session_manager_pb2.GetSessionResponse(
            session_active=True,
            simulator_endpoint=simulator_endpoint
        )
    
    def end_session(self, request, context):
        session_id = request.session_id
        token = request.token
        
        # Validate token and session access
        user_id = self.session_service.validate_session_access(token, session_id)
        if not user_id:
            logger.warning(f"Invalid session access in EndSession for {session_id}")
            return session_manager_pb2.EndSessionResponse(
                success=False,
                error_message="Invalid session or authentication"
            )
        
        # Delete session
        logger.info(f"Ending session {session_id} for user {user_id}")
        self.session_service.delete_session(session_id, user_id)
        
        return session_manager_pb2.EndSessionResponse(success=True)
    
    def keep_alive(self, request, context):
        session_id = request.session_id
        token = request.token
        
        # Validate token and session access
        user_id = self.session_service.validate_session_access(token, session_id)
        if not user_id:
            logger.warning(f"Invalid session access in KeepAlive for {session_id}")
            return session_manager_pb2.KeepAliveResponse(success=False)
        
        # Update session activity
        self.db.update_session_activity(session_id)
        
        # Check if we have an active exchange service and ping it if we do
        exchange_info = self.db.get_exchange_for_session(session_id)
        if exchange_info:
            # Update exchange last active too
            self.db.update_exchange_last_active(session_id)
        
        return session_manager_pb2.KeepAliveResponse(success=True)
    
    def get_session_state(self, request, context):
        session_id = request.session_id
        token = request.token
        
        # Validate token and session access
        user_id = self.session_service.validate_session_access(token, session_id)
        if not user_id:
            logger.warning(f"Invalid session access in GetSessionState for {session_id}")
            return session_manager_pb2.GetSessionStateResponse(
                success=False,
                error_message="Invalid session or authentication"
            )
        
        # Get session data
        session_data = self.session_service.get_session_data(session_id)
        
        # Update session activity
        self.db.update_session_activity(session_id)
        
        # Get exchange connection state
        exchange_active = self.session_service.exchange_manager.is_exchange_connected(session_id)
        
        # Return session state
        return session_manager_pb2.GetSessionStateResponse(
            success=True,
            simulator_id=session_data.get("simulator_id") or "",
            simulator_endpoint=session_data.get("simulator_endpoint") or "",
            session_created_at=int(session_data.get("created_at", 0)),
            last_active=int(session_data.get("last_active", 0)),
            exchange_connected=exchange_active,
            session_host=self.session_service.pod_name  # Include the pod name hosting the session
        )
    
    def reconnect_session(self, request, context):
        session_id = request.session_id
        token = request.token
        reconnect_attempt = request.reconnect_attempt
        
        logger.info(f"Reconnection attempt {reconnect_attempt} for session {session_id}")
        
        # Validate token
        user_id = self.session_service.validate_token(token)
        if not user_id:
            logger.warning(f"Invalid token during ReconnectSession for {session_id}")
            return session_manager_pb2.ReconnectSessionResponse(
                success=False,
                error_message="Invalid authentication token"
            )
        
        # Check if the session was previously connected to a different pod
        previous_pod = None
        is_pod_transfer = False
        
        # Get session data
        session_data = self.session_service.get_session_data(session_id)
        
        if not session_data:
            logger.warning(f"Session {session_id} not found during ReconnectSession")
            # Try to create a new session
            new_session_id = str(uuid.uuid4())
            success = self.db.create_session(new_session_id, user_id, self.get_client_ip(context))
            
            if success:
                # Update pod hosting info
                self.db.update_session_metadata(new_session_id, {
                    "session_host": self.session_service.pod_name
                })
                
                return session_manager_pb2.ReconnectSessionResponse(
                    success=True,
                    session_id=new_session_id,
                    error_message="Created new session"
                )
            else:
                return session_manager_pb2.ReconnectSessionResponse(
                    success=False,
                    error_message="Session not found and could not create new session"
                )
        
        # Check if session belongs to requesting user
        if str(session_data.get("user_id")) != user_id:
            logger.warning(f"Session {session_id} does not belong to user {user_id}")
            return session_manager_pb2.ReconnectSessionResponse(
                success=False,
                error_message="Session does not belong to user"
            )
        
        # Check pod transfer
        previous_pod = session_data.get("session_host")
        if previous_pod and previous_pod != self.session_service.pod_name:
            is_pod_transfer = True
            logger.info(f"Session {session_id} transferred from pod {previous_pod} to {self.session_service.pod_name}")
        
        # Check if session has expired
        if session_data.get("expires_at") and session_data["expires_at"] < time.time():
            # Session expired, try to create a new one
            logger.info(f"Session {session_id} has expired during reconnection attempt")
            new_session_id = str(uuid.uuid4())
            success = self.db.create_session(new_session_id, user_id, self.get_client_ip(context))
            
            if success:
                # Update pod hosting info
                self.db.update_session_metadata(new_session_id, {
                    "session_host": self.session_service.pod_name
                })
                
                return session_manager_pb2.ReconnectSessionResponse(
                    success=True,
                    session_id=new_session_id,
                    error_message="Created new session after expiration"
                )
            else:
                return session_manager_pb2.ReconnectSessionResponse(
                    success=False,
                    error_message="Session expired and could not create new session"
                )
        
        # Update session activity
        self.db.update_session_activity(session_id)
        
        # Update the hosting pod information
        self.db.update_session_metadata(session_id, {
            "session_host": self.session_service.pod_name
        })
        
        # Get simulator info
        simulator_id = session_data.get("simulator_id", "")
        simulator_endpoint = session_data.get("simulator_endpoint", "")
        
        # Check if we have an active exchange - don't activate it yet until needed
        exchange_active = self.session_service.exchange_manager.is_exchange_connected(session_id)
        simulator_status = "RUNNING" if exchange_active else "UNKNOWN"
        
        return session_manager_pb2.ReconnectSessionResponse(
            success=True,
            session_id=session_id,
            simulator_id=simulator_id,
            simulator_endpoint=simulator_endpoint,
            simulator_status=simulator_status,
            pod_transferred=is_pod_transfer
        )
    
    def update_connection_quality(self, request, context):
        session_id = request.session_id
        token = request.token
        latency_ms = request.latency_ms
        missed_heartbeats = request.missed_heartbeats
        connection_type = request.connection_type
        
        # Validate token and session
        user_id = self.session_service.validate_session_access(token, session_id)
        if not user_id:
            logger.warning(f"Invalid session access in UpdateConnectionQuality for {session_id}")
            return session_manager_pb2.ConnectionQualityResponse(
                quality="poor",
                reconnect_recommended=True
            )
        
        # Determine connection quality
        quality = "good"
        reconnect_recommended = False
        
        if missed_heartbeats >= 3:
            quality = "poor"
            reconnect_recommended = True
        elif missed_heartbeats > 0 or latency_ms > 500:
            quality = "degraded"
            reconnect_recommended = missed_heartbeats >= 2
        
        # Store metrics in database
        self.db.update_session_metadata(session_id, {
            "connection_quality": {
                "latency_ms": latency_ms,
                "missed_heartbeats": missed_heartbeats,
                "connection_type": connection_type,
                "quality": quality,
                "timestamp": time.time()
            }
        })
        
        return session_manager_pb2.ConnectionQualityResponse(
            quality=quality,
            reconnect_recommended=reconnect_recommended
        )