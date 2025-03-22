# exchange_manager.py
import logging
import time
import threading
import grpc
import os
import uuid
import requests
from datetime import datetime, timezone

import exchange_pb2
import exchange_pb2_grpc

logger = logging.getLogger('exchange_manager')

# Get environment configuration
KUBERNETES_NAMESPACE = os.getenv('KUBERNETES_NAMESPACE', 'default')
EXCHANGE_SERVICE_FORMAT = os.getenv('EXCHANGE_SERVICE_FORMAT', '{exchange_id}.exchange.{namespace}.svc.cluster.local:50053')
SIMULATOR_MANAGER_URL = os.getenv('SIMULATOR_MANAGER_URL', 'http://simulator-manager:8080')

class ExchangeManager:
    """Manages lifecycle and connections to exchange services"""
    
    def __init__(self, session_service):
        self.session_service = session_service
        self.db = session_service.db
        self.lock = threading.RLock()
        self.exchange_connections = {}  # session_id -> connection info
        self.frontend_streams = {}      # session_id -> list of frontend stream contexts
        
        # Timeouts and thresholds
        self.exchange_ping_interval = 30  # seconds
        self.default_inactivity_timeout = 300  # seconds (5 minutes)
        
        # Start exchange service cleanup thread
        self.cleanup_thread = threading.Thread(target=self.cleanup_inactive_exchanges, daemon=True)
        self.cleanup_thread.start()
    
    def activate_session(self, session_id, user_id):
        """Ensure a session has an active exchange service"""
        # Check if exchange service exists
        exchange_info = self.db.get_exchange_for_session(session_id)
        
        if exchange_info:
            # Update last active timestamp
            self.db.update_exchange_last_active(session_id)
            return exchange_info['exchange_id'], exchange_info['endpoint']
        else:
            # Launch new exchange service
            exchange_id, exchange_endpoint = self._launch_exchange_service(session_id, user_id)
            
            if exchange_id and exchange_endpoint:
                # Register in database with timeout setting
                self.db.register_exchange_service(
                    session_id=session_id,
                    exchange_id=exchange_id,
                    endpoint=exchange_endpoint,
                    inactivity_timeout_seconds=self.default_inactivity_timeout
                )
                
                # Update session metadata
                self.session_service.update_session_metadata(session_id, {
                    "simulator_id": exchange_id,
                    "simulator_endpoint": exchange_endpoint
                })
                
                return exchange_id, exchange_endpoint
            
            return None, None
    
    def _launch_exchange_service(self, session_id, user_id):
        """Launch a new exchange service instance"""
        logger.info(f"Launching new exchange service for session {session_id}")
        
        try:
            # Generate exchange ID
            exchange_id = str(uuid.uuid4())
            
            # In production: Call simulator manager service to start a new simulator
            # For now, simulate the API call
            response = self._call_simulator_manager_api(session_id, user_id)
            
            if response and response.get('success'):
                exchange_endpoint = response.get('endpoint')
                logger.info(f"New exchange service started: {exchange_id} at {exchange_endpoint}")
                return exchange_id, exchange_endpoint
            else:
                logger.error(f"Failed to start exchange service: {response.get('error', 'Unknown error')}")
                return None, None
                
        except Exception as e:
            logger.error(f"Error launching exchange service: {e}")
            return None, None
    
    def _call_simulator_manager_api(self, session_id, user_id):
        """Call simulator manager API to start a new simulator"""
        # In production: This would be a real API call
        # For now, simulate a successful response
        try:
            # Real API call example:
            # response = requests.post(
            #     f"{SIMULATOR_MANAGER_URL}/api/simulators",
            #     json={
            #         "session_id": session_id,
            #         "user_id": user_id
            #     },
            #     headers={
            #         "Content-Type": "application/json"
            #     },
            #     timeout=10
            # )
            # if response.status_code == 200:
            #     return response.json()
            # return {"success": False, "error": f"API error: {response.status_code}"}
            
            # Simulate successful response
            exchange_id = str(uuid.uuid4())
            exchange_endpoint = EXCHANGE_SERVICE_FORMAT.format(
                exchange_id=exchange_id,
                namespace=KUBERNETES_NAMESPACE
            )
            return {
                "success": True,
                "exchange_id": exchange_id,
                "endpoint": exchange_endpoint
            }
        except Exception as e:
            logger.error(f"Error calling simulator manager API: {e}")
            return {"success": False, "error": str(e)}
    
    def _terminate_exchange_service(self, exchange_id):
        """Terminate an exchange service"""
        logger.info(f"Terminating exchange service {exchange_id}")
        
        try:
            # In production: Call simulator manager API to terminate
            # For now, simulate the API call
            
            # Real API call example:
            # response = requests.delete(
            #     f"{SIMULATOR_MANAGER_URL}/api/simulators/{exchange_id}",
            #     timeout=10
            # )
            # return response.status_code == 200
            
            # Simulate successful termination
            return True
        except Exception as e:
            logger.error(f"Error terminating exchange service {exchange_id}: {e}")
            return False
    
    def ping_exchange_service(self, session_id):
        """Send heartbeat to exchange service and update last activity"""
        # Update last_active timestamp in database
        self.db.update_exchange_last_active(session_id)
        
        # If we have an active connection, send heartbeat
        with self.lock:
            if session_id in self.exchange_connections and self.exchange_connections[session_id]['active']:
                try:
                    connection = self.exchange_connections[session_id]
                    heartbeat_request = exchange_pb2.HeartbeatRequest(
                        session_id=session_id,
                        client_id=connection['client_id'],
                        client_timestamp=int(time.time() * 1000)
                    )
                    
                    # Send request with timeout
                    heartbeat_response = connection['stub'].Heartbeat(
                        heartbeat_request, 
                        timeout=5  # 5 seconds timeout
                    )
                    
                    return heartbeat_response.success
                except Exception as e:
                    logger.error(f"Error sending heartbeat to exchange: {e}")
                    return False
                    
        # Get exchange info from database if no active connection
        exchange_info = self.db.get_exchange_for_session(session_id)
        if not exchange_info:
            return False
            
        # Try to establish connection
        try:
            # Create gRPC channel
            channel = grpc.insecure_channel(exchange_info['endpoint'])
            stub = exchange_pb2_grpc.ExchangeSimulatorStub(channel)
            
            # Create client ID
            client_id = f"session_manager_{session_id}_{int(time.time())}"
            
            # Send heartbeat
            heartbeat_request = exchange_pb2.HeartbeatRequest(
                session_id=session_id,
                client_id=client_id,
                client_timestamp=int(time.time() * 1000)
            )
            
            heartbeat_response = stub.Heartbeat(
                heartbeat_request, 
                timeout=5
            )
            
            # Close channel
            channel.close()
            
            return heartbeat_response.success
        except Exception as e:
            logger.error(f"Error pinging exchange service for session {session_id}: {e}")
            return False
    
    def cleanup_inactive_exchanges(self):
        """Process that runs periodically to terminate inactive exchange services"""
        while True:
            try:
                time.sleep(60)  # Check every minute
                logger.info("Running exchange service cleanup check")
                
                # Get all exchange services with their timeout settings
                exchange_services = self.db.get_all_exchange_services()
                
                for service in exchange_services:
                    # Calculate time since last activity
                    last_active = service['last_active']
                    timeout_seconds = service['inactivity_timeout_seconds']
                    current_time = datetime.now(timezone.utc)
                    
                    # If inactive beyond timeout, terminate
                    if (current_time - last_active).total_seconds() > timeout_seconds:
                        logger.info(f"Terminating inactive exchange service {service['exchange_id']} for session {service['session_id']}")
                        
                        # Close any active connection
                        with self.lock:
                            if service['session_id'] in self.exchange_connections:
                                self._close_exchange_connection(service['session_id'])
                        
                        # Call termination API
                        self._terminate_exchange_service(service['exchange_id'])
                        
                        # Update database
                        self.db.deactivate_exchange_service(service['exchange_id'])
            except Exception as e:
                logger.error(f"Error in exchange service cleanup: {e}")
    
    def is_exchange_connected(self, session_id):
        """Check if an exchange connection is active for the session"""
        with self.lock:
            if session_id in self.exchange_connections:
                return self.exchange_connections[session_id]['active']
        
        # Check database
        exchange_info = self.db.get_exchange_for_session(session_id)
        return exchange_info is not None
    
    def _close_exchange_connection(self, session_id):
        """Close an active exchange connection"""
        with self.lock:
            if session_id in self.exchange_connections:
                connection = self.exchange_connections[session_id]
                
                # Set as inactive
                connection['active'] = False
                
                # Cancel any pending streams
                self._cancel_streams(session_id)
                
                # Close gRPC channel
                try:
                    connection['channel'].close()
                except Exception as e:
                    logger.error(f"Error closing exchange channel for {session_id}: {e}")
                
                # Remove from tracking
                del self.exchange_connections[session_id]
                logger.info(f"Closed exchange connection for session {session_id}")
    
    def _cancel_streams(self, session_id):
        """Cancel all frontend streams for a session"""
        with self.lock:
            if session_id not in self.frontend_streams:
                return
            
            # Get all streams
            streams = list(self.frontend_streams[session_id])
            
            # Clear the list
            self.frontend_streams[session_id] = []
        
        # Cancel each stream
        for stream_context in streams:
            try:
                if stream_context.is_active():
                    stream_context.abort(grpc.StatusCode.CANCELLED, "Exchange connection closed")
            except Exception as e:
                logger.error(f"Error cancelling frontend stream: {e}")
    
    def stream_exchange_data(self, session_id, user_id, request, context):
        """Stream exchange data to frontend client"""
        symbols = list(request.symbols) if hasattr(request, 'symbols') else []
        
        logger.info(f"Frontend requesting exchange data stream for session {session_id}")
        
        # Register frontend stream
        with self.lock:
            if session_id not in self.frontend_streams:
                self.frontend_streams[session_id] = []
            
            # Add frontend stream
            self.frontend_streams[session_id].append(context)
            
            # Get exchange service info
            exchange_info = self.db.get_exchange_for_session(session_id)
            if not exchange_info:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "No exchange service available")
                return
            
            # Check if we have an active connection
            exchange_connected = session_id in self.exchange_connections and self.exchange_connections[session_id]['active']
            if not exchange_connected:
                # Create exchange connection
                exchange_endpoint = exchange_info['endpoint']
                try:
                    self._create_exchange_connection(session_id, exchange_endpoint, symbols)
                except Exception as e:
                    logger.error(f"Failed to connect to exchange for session {session_id}: {e}")
                    context.abort(grpc.StatusCode.UNAVAILABLE, f"Exchange connection failed: {str(e)}")
                    return
        
        # Register cleanup callback
        def on_frontend_stream_closed():
            with self.lock:
                if session_id in self.frontend_streams:
                    if context in self.frontend_streams[session_id]:
                        self.frontend_streams[session_id].remove(context)
                        logger.info(f"Frontend stream closed for session {session_id}, {len(self.frontend_streams[session_id])} streams remaining")
        
        context.add_callback(on_frontend_stream_closed)
        
        # Keep stream open until client disconnects
        try:
            # Keep context alive - actual data is forwarded in exchange stream thread
            while context.is_active():
                # Ping exchange connection periodically if this is the sole frontend stream
                with self.lock:
                    is_sole_frontend = session_id in self.frontend_streams and len(self.frontend_streams[session_id]) == 1
                
                if is_sole_frontend:
                    self.ping_exchange_service(session_id)
                
                time.sleep(self.exchange_ping_interval)
        except Exception as e:
            logger.error(f"Error in frontend stream for session {session_id}: {e}")
    
    def _create_exchange_connection(self, session_id, exchange_endpoint, symbols):
        """Create a connection to an exchange endpoint"""
        logger.info(f"Creating exchange connection for session {session_id} to {exchange_endpoint}")
        
        try:
            # Get session data for client ID
            session_data = self.session_service.get_session_data(session_id)
            if not session_data:
                raise Exception("Session data not found")
            
            # Generate client ID
            user_id = session_data.get("user_id")
            client_id = f"client_{user_id}_{int(time.time())}"
            
            # Create gRPC channel with keepalive options for better reliability in EKS
            channel_options = [
                ('grpc.keepalive_time_ms', 10000),  # Send keepalive ping every 10 seconds
                ('grpc.keepalive_timeout_ms', 5000),  # 5 seconds timeout for keepalive ping
                ('grpc.keepalive_permit_without_calls', 1),  # Allow keepalive pings when no calls are in flight
                ('grpc.http2.max_pings_without_data', 0),  # Allow unlimited pings without data
                ('grpc.http2.min_time_between_pings_ms', 10000),  # Minimum time between pings
                ('grpc.http2.min_ping_interval_without_data_ms', 5000)  # Minimum time between pings when no data
            ]
            exchange_channel = grpc.insecure_channel(exchange_endpoint, options=channel_options)
            exchange_stub = exchange_pb2_grpc.ExchangeSimulatorStub(exchange_channel)
            
            # Prepare request
            exchange_request = exchange_pb2.StreamRequest(
                session_id=session_id,
                client_id=client_id,
                symbols=symbols
            )
            
            # Create connection entry
            connection = {
                'channel': exchange_channel,
                'stub': exchange_stub,
                'client_id': client_id,
                'thread': threading.Thread(
                    target=self._handle_exchange_stream,
                    args=(session_id, exchange_stub, exchange_request),
                    daemon=True
                ),
                'active': True,
                'last_data': time.time()
            }
            
            # Start exchange thread
            with self.lock:
                # Close any existing connection
                if session_id in self.exchange_connections:
                    self._close_exchange_connection(session_id)
                
                # Store new connection
                self.exchange_connections[session_id] = connection
            
            # Start the thread
            connection['thread'].start()
            
            # Update session with client ID
            self.session_service.update_session_metadata(session_id, {
                "exchange_client_id": client_id
            })
            
            # Update database with last activity
            self.db.update_exchange_last_active(session_id)
            
            return connection
            
        except Exception as e:
            logger.error(f"Error creating exchange connection: {e}")
            raise
    
    def _handle_exchange_stream(self, session_id, exchange_stub, request):
        """Handle streaming data from exchange"""
        try:
            logger.info(f"Starting exchange stream for session {session_id}")
            
            # Start streaming from exchange
            exchange_stream = exchange_stub.StreamExchangeData(request)
            
            # Process incoming data
            for exchange_data in exchange_stream:
                # Update last data timestamp
                with self.lock:
                    if session_id in self.exchange_connections:
                        self.exchange_connections[session_id]['last_data'] = time.time()
                        
                        # Forward data to all frontend streams
                        self._forward_to_frontends(session_id, exchange_data)
                    else:
                        # Connection was closed
                        break
                
                # Update last active in database periodically
                if int(time.time()) % 10 == 0:  # Every 10 seconds
                    self.db.update_exchange_last_active(session_id)
        
        except Exception as e:
            logger.error(f"Error in exchange stream for session {session_id}: {e}")
        
        finally:
            # Mark connection as inactive
            with self.lock:
                if session_id in self.exchange_connections:
                    self.exchange_connections[session_id]['active'] = False
                    logger.info(f"Exchange stream ended for session {session_id}")
    
    def _forward_to_frontends(self, session_id, exchange_data):
        """Forward exchange data to all frontend streams"""
        with self.lock:
            if session_id not in self.frontend_streams:
                return
            
            frontend_streams = list(self.frontend_streams[session_id])
        
        # Send to each frontend stream
        for stream_context in frontend_streams:
            try:
                if stream_context.is_active():
                    stream_context.write(exchange_data)
                else:
                    # Stream is not active, remove it
                    with self.lock:
                        if session_id in self.frontend_streams and stream_context in self.frontend_streams[session_id]:
                            self.frontend_streams[session_id].remove(stream_context)
            except Exception as e:
                logger.error(f"Error forwarding data to frontend for session {session_id}: {e}")
                # Remove problematic frontend stream
                with self.lock:
                    if session_id in self.frontend_streams and stream_context in self.frontend_streams[session_id]:
                        self.frontend_streams[session_id].remove(stream_context)