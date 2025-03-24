# session-manager-service/source/server.py

import asyncio
import logging
import os
import signal
import socket
import json
import time
from aiohttp import web
import aiohttp_cors
import redis.asyncio as redis

# Import API components
from rest.routes import setup_routes
from rest.handlers import (
    handle_create_session, handle_get_session, handle_end_session,
    handle_keep_alive, handle_start_simulator, handle_stop_simulator,
    handle_get_simulator_status, handle_reconnect_session
)

# Import WebSocket components
from websocket.manager import WebSocketManager
from websocket.protocol import WebSocketProtocol

# Import SSE components
from sse.stream import setup_sse_routes
from sse.adapter import SSEAdapter

# Import core classes
from core.session_manager import SessionManager
from session.state import SessionState, SessionStatus, SimulatorStatus

# Import API client for auth service
from api.auth_client import AuthClient

# Import gRPC client for exchange
from core.exchange_client import ExchangeServiceClient

# Import database manager
from db.session_store import DatabaseManager

# Import configuration
from config import setup_logging, config

# Configure logging
setup_logging()
logger = logging.getLogger('session_service')

class SessionServer:
    def __init__(self):
        self.app = web.Application()
        self.host = config.HOST
        self.port = config.PORT
        self.pod_name = os.getenv('POD_NAME', socket.gethostname())
        self.running = True
        
        logger.info(f"Initializing session service on pod {self.pod_name}")
    
    def setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown"""
        for sig in (signal.SIGTERM, signal.SIGINT):
            asyncio.get_event_loop().add_signal_handler(
                sig, lambda s=sig: asyncio.create_task(self.shutdown(s)))
    
    async def init_redis(self):
        """Initialize Redis connection"""
        redis_host = os.getenv('REDIS_HOST', 'redis')
        redis_port = int(os.getenv('REDIS_PORT', '6379'))
        redis_password = os.getenv('REDIS_PASSWORD', '')
        redis_db = int(os.getenv('REDIS_DB', '0'))
        
        try:
            # Create Redis client
            redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                db=redis_db,
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
                retry_on_timeout=True
            )
            
            # Test connection
            await redis_client.ping()
            logger.info("Connected to Redis successfully")
            return redis_client
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            # Continue without Redis - it's used for enhanced features but not required
            return None
    
    async def register_pod(self):
        """Register this pod with Redis"""
        if not self.redis:
            return
        
        try:
            # Store pod info
            pod_info = {
                'name': self.pod_name,
                'host': self.host,
                'port': self.port,
                'started_at': time.time(),
                'last_heartbeat': time.time()
            }
            
            # Store as hash
            await self.redis.hset(f'pod:{self.pod_name}', mapping=pod_info)
            await self.redis.expire(f'pod:{self.pod_name}', 3600)  # 1 hour TTL
            
            # Add to active pods set
            await self.redis.sadd('active_pods', self.pod_name)
            
            # Publish pod online event
            await self.redis.publish('session_events', json.dumps({
                'type': 'pod_online',
                'pod_name': self.pod_name,
                'timestamp': time.time()
            }))
            
            # Start pod heartbeat task
            self.pod_heartbeat_task = asyncio.create_task(self.pod_heartbeat())
            
            logger.info(f"Registered pod {self.pod_name} with Redis")
        except Exception as e:
            logger.error(f"Error registering pod with Redis: {e}")
    
    async def pod_heartbeat(self):
        """Periodically update pod heartbeat in Redis"""
        if not self.redis:
            return
        
        while self.running:
            try:
                # Update heartbeat
                await self.redis.hset(f'pod:{self.pod_name}', 'last_heartbeat', time.time())
                await self.redis.expire(f'pod:{self.pod_name}', 3600)  # Refresh TTL
                
                # Wait for next heartbeat
                await asyncio.sleep(30)  # Every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in pod heartbeat: {e}")
                await asyncio.sleep(10)  # Shorter interval on error
    
    async def setup_pubsub(self):
        """Set up Redis pub/sub for cross-pod communication"""
        if not self.redis:
            return
        
        try:
            # Create pub/sub subscription
            self.pubsub = self.redis.pubsub()
            await self.pubsub.subscribe('session_events')
            
            # Start processing messages
            self.pubsub_task = asyncio.create_task(self.process_pubsub_messages())
            logger.info("Redis pub/sub initialized successfully")
        except Exception as e:
            logger.error(f"Failed to setup Redis pub/sub: {e}")
    
    async def process_pubsub_messages(self):
        """Process messages from Redis pub/sub channel"""
        if not self.redis or not hasattr(self, 'pubsub'):
            return
        
        while self.running:
            try:
                message = await self.pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message['type'] == 'message':
                    await self.handle_pubsub_message(message)
                
                # Small sleep to avoid CPU spinning
                await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing pubsub messages: {e}")
                await asyncio.sleep(1)
    
    async def handle_pubsub_message(self, message):
        """Handle a message from Redis pub/sub"""
        try:
            data = json.loads(message['data'])
            event_type = data.get('type')
            
            # Skip our own messages
            if data.get('pod_name') == self.pod_name:
                return
            
            # Handle different event types
            if event_type == 'session_created' or event_type == 'session_resumed':
                # Another pod created or resumed a session
                logger.debug(f"Session {data.get('session_id')} {event_type} on pod {data.get('pod_name')}")
            
            elif event_type == 'client_connected':
                # Client connected to another pod
                session_id = data.get('session_id')
                logger.debug(f"Client connected to session {session_id} on pod {data.get('pod_name')}")
            
            elif event_type == 'client_disconnected':
                # Client disconnected from another pod
                session_id = data.get('session_id')
                logger.debug(f"Client disconnected from session {session_id} on pod {data.get('pod_name')}")
            
            elif event_type == 'pod_online':
                # Another pod came online
                logger.info(f"Pod {data.get('pod_name')} came online")
            
            elif event_type == 'pod_offline':
                # Another pod went offline
                logger.info(f"Pod {data.get('pod_name')} went offline")
                
                # Check if we need to take over any sessions from the offline pod
                await self.handle_orphaned_sessions(data.get('pod_name'))
            
            elif event_type == 'simulator_started':
                # A simulator was started
                session_id = data.get('session_id')
                simulator_id = data.get('simulator_id')
                logger.info(f"Simulator {simulator_id} started for session {session_id}")
                
                # If this is a session we're managing, notify connected clients
                if self.websocket_manager and session_id:
                    await self.websocket_manager.broadcast_to_session(
                        session_id,
                        {
                            'type': 'simulator_update',
                            'status': 'STARTING',
                            'simulatorId': simulator_id
                        }
                    )
            
            elif event_type == 'simulator_stopped':
                # A simulator was stopped
                session_id = data.get('session_id')
                simulator_id = data.get('simulator_id')
                logger.info(f"Simulator {simulator_id} stopped for session {session_id}")
                
                # If this is a session we're managing, notify connected clients
                if self.websocket_manager and session_id:
                    await self.websocket_manager.broadcast_to_session(
                        session_id,
                        {
                            'type': 'simulator_update',
                            'status': 'STOPPED',
                            'simulatorId': simulator_id
                        }
                    )
        except Exception as e:
            logger.error(f"Error handling pub/sub message: {e}")
    
    async def handle_orphaned_sessions(self, offline_pod_name):
        """Handle sessions orphaned by an offline pod"""
        if not self.redis:
            return
        
        try:
            # Get sessions that were managed by the offline pod
            orphaned_sessions = await self.redis.smembers(f'pod:{offline_pod_name}:sessions')
            
            if not orphaned_sessions:
                return
            
            logger.info(f"Found {len(orphaned_sessions)} orphaned sessions from pod {offline_pod_name}")
            
            # For each orphaned session, check if it has active clients
            for session_id in orphaned_sessions:
                # Check if session has active WebSocket connections
                ws_count = await self.redis.get(f'connection:{session_id}:ws_count')
                
                if ws_count and int(ws_count) > 0:
                    logger.info(f"Taking over orphaned session {session_id} with {ws_count} active connections")
                    
                    # Update session metadata to point to this pod
                    await self.db_manager.update_session_metadata(session_id, {
                        'session_host': self.pod_name,
                        'previous_host': offline_pod_name,
                        'host_transfer_time': time.time()
                    })
                    
                    # Update Redis
                    await self.redis.set(f'session:{session_id}:pod', self.pod_name, ex=3600)
                    await self.redis.sadd(f'pod:{self.pod_name}:sessions', session_id)
                    
                    # Publish event
                    await self.redis.publish('session_events', json.dumps({
                        'type': 'session_transferred',
                        'session_id': session_id,
                        'from_pod': offline_pod_name,
                        'to_pod': self.pod_name,
                        'timestamp': time.time()
                    }))
        except Exception as e:
            logger.error(f"Error handling orphaned sessions: {e}")
    
    async def init_components(self):
        """Initialize all service components"""
        # Initialize Redis first
        self.redis = await self.init_redis()
        
        # Database connection
        self.db_manager = DatabaseManager()
        await self.db_manager.connect()
        
        # Initialize auth client with proper URL - UPDATED to use REST API
        self.auth_client = AuthClient(config.AUTH_SERVICE_URL)
        await self.auth_client.connect()
        
        # Exchange gRPC client
        self.exchange_client = ExchangeServiceClient()
        
        # Session manager - inject dependencies
        self.session_manager = SessionManager(
            self.db_manager, 
            self.auth_client,
            self.exchange_client,
            pod_name=self.pod_name
        )
        self.session_manager.redis = self.redis  # Add Redis reference
        
        # SSE adapter - inject Redis
        self.sse_adapter = SSEAdapter(self.exchange_client)
        self.sse_adapter.redis = self.redis  # Add Redis reference
        
        # WebSocket protocol handler
        self.ws_protocol = WebSocketProtocol(self.session_manager)
        self.ws_protocol.redis = self.redis  # Add Redis reference
        
        # WebSocket manager - inject Redis
        self.websocket_manager = WebSocketManager(
            self.session_manager,
            self.ws_protocol
        )
        self.websocket_manager.redis = self.redis  # Add Redis reference
        
        # Register circuit breaker state change listeners
        if hasattr(self.websocket_manager, 'circuit_breakers'):
            for name, circuit_breaker in self.websocket_manager.circuit_breakers.items():
                circuit_breaker.on_state_change(self._handle_circuit_breaker_state_change)
        
        # Set up Redis pub/sub
        await self.setup_pubsub()
        
        # Register this pod with Redis
        await self.register_pod()
        
        # Store components in app for access in request handlers
        self.app['db_manager'] = self.db_manager
        self.app['session_manager'] = self.session_manager
        self.app['websocket_manager'] = self.websocket_manager
        self.app['auth_client'] = self.auth_client
        self.app['exchange_client'] = self.exchange_client
        self.app['sse_adapter'] = self.sse_adapter
        self.app['redis'] = self.redis
    
    def setup_routes(self):
        """Set up all API routes"""
        # REST API routes
        self.app.router.add_post('/api/session', handle_create_session)
        self.app.router.add_get('/api/session/{session_id}', handle_get_session)
        self.app.router.add_delete('/api/session/{session_id}', handle_end_session)
        self.app.router.add_post('/api/session/{session_id}/keep-alive', handle_keep_alive)
        
        # Simulator routes
        self.app.router.add_post('/api/simulator', handle_start_simulator)
        self.app.router.add_delete('/api/simulator/{simulator_id}', handle_stop_simulator)
        self.app.router.add_get('/api/simulator/{simulator_id}', handle_get_simulator_status)
        self.app.router.add_post('/api/session/{session_id}/reconnect', handle_reconnect_session)
        
        # SSE routes
        setup_sse_routes(self.app)
        
        # WebSocket route
        self.app.router.add_get('/ws', self.websocket_manager.websocket_handler)
        
        # Health check routes
        self.app.router.add_get('/health', self.health_handler)
        self.app.router.add_get('/readiness', self.readiness_handler)
    
    def setup_cors(self):
        """Configure CORS for API endpoints"""
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
            )
        })
        
        # Apply CORS to all routes
        for route in list(self.app.router.routes()):
            cors.add(route)
    
    async def health_handler(self, request):
        """Simple health check endpoint"""
        # Check Redis health if available
        redis_health = "OK"
        if hasattr(self, 'redis') and self.redis:
            try:
                await self.redis.ping()
            except Exception as e:
                redis_health = f"ERROR: {str(e)}"
        
        health_data = {
            "status": "OK",
            "pod": self.pod_name,
            "timestamp": time.time(),
            "redis": redis_health,
            "connections": len(getattr(self.websocket_manager, 'connections', {}))
        }
        
        return web.json_response(health_data)
    
    # Add a new method to handle circuit breaker state changes
    async def _handle_circuit_breaker_state_change(self, circuit_name, old_state, new_state, state_info):
        """Handle circuit breaker state change"""
        logger.warning(f"Circuit breaker '{circuit_name}' changed from {old_state.value} to {new_state.value}")
        
        # Publish circuit breaker state change to Redis
        if self.redis:
            try:
                await self.redis.publish('session_events', json.dumps({
                    'type': 'circuit_breaker_change',
                    'pod_name': self.pod_name,
                    'circuit_name': circuit_name,
                    'old_state': old_state.value,
                    'new_state': new_state.value,
                    'info': state_info,
                    'timestamp': time.time()
                }))
            except Exception as e:
                logger.error(f"Error publishing circuit breaker state change: {e}")
        
        # Broadcast to all connected clients
        await self.websocket_manager.broadcast_circuit_breaker_update(circuit_name, state_info)
        
        # If a critical service becomes available again, try to recover any failed operations
        if hasattr(old_state, 'value') and hasattr(new_state, 'value'):
            if old_state.value != "CLOSED" and new_state.value == "CLOSED":
                logger.info(f"Circuit '{circuit_name}' closed, attempting recovery operations")
                # Implement recovery logic here if needed
            
    async def readiness_handler(self, request):
        """Readiness check endpoint"""
        # Check all dependencies are available
        checks_ok = all([
            await self.db_manager.check_connection(),
            await self.auth_client.check_service()
        ])
        
        if checks_ok:
            return web.Response(text="READY", status=200)
        else:
            return web.Response(text="NOT READY", status=503)
    
    async def shutdown(self, signal=None):
        """Gracefully shut down the server"""
        if signal:
            logger.info(f"Received shutdown signal {signal.name}")
        
        self.running = False
        
        # Cancel background tasks
        if hasattr(self, 'pod_heartbeat_task'):
            self.pod_heartbeat_task.cancel()
            try:
                await self.pod_heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if hasattr(self, 'pubsub_task'):
            self.pubsub_task.cancel()
            try:
                await self.pubsub_task
            except asyncio.CancelledError:
                pass
        
        # Unsubscribe from Redis pubsub
        if hasattr(self, 'pubsub') and self.pubsub:
            await self.pubsub.unsubscribe()
        
        # Publish pod offline event
        if self.redis:
            try:
                await self.redis.publish('session_events', json.dumps({
                    'type': 'pod_offline',
                    'pod_name': self.pod_name,
                    'timestamp': time.time()
                }))
                
                # Remove from active pods
                await self.redis.srem('active_pods', self.pod_name)
                
                # Close Redis connection
                await self.redis.close()
            except Exception as e:
                logger.error(f"Error during Redis shutdown: {e}")
        
        # Close all client connections
        await self.websocket_manager.close_all_connections(
            reason="Server shutting down")
        
        # Close SSE streams
        await self.sse_adapter.close_all_streams()
        
        # Close gRPC clients
        await self.auth_client.close()
        
        # Close database connections
        await self.db_manager.close()
        
        # Stop the web server
        logger.info("Shutdown complete")
        
    async def init_ssl_context(self):
        """Initialize SSL context for HTTPS and WSS"""
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        
        # Check if we're running in Kubernetes with mounted secrets
        cert_path = os.environ.get('TLS_CERT_PATH', './certs')
        
        try:
            ssl_context.load_cert_chain(
                f"{cert_path}/server.crt",
                f"{cert_path}/server.key"
            )
            # For mutual TLS (if needed)
            ssl_context.load_verify_locations(f"{cert_path}/ca.crt")
            
            # Verify client certificates for mutual TLS
            if os.environ.get('REQUIRE_CLIENT_CERT', 'false').lower() == 'true':
                ssl_context.verify_mode = ssl.CERT_REQUIRED
            
            logger.info("SSL context initialized successfully")
            return ssl_context
        except Exception as e:
            logger.error(f"Failed to initialize SSL context: {e}")
            # Return None for local development without TLS
            return None

    async def start(self):
        """Initialize and start the server"""
        # Setup signal handlers
        self.setup_signal_handlers()
        
        # Initialize components
        await self.init_components()
        
        # Setup routes and middleware
        self.setup_routes()
        self.setup_cors()
        
        # Initialize SSL context
        ssl_context = await self.init_ssl_context()
        
        # Start the server
        runner = web.AppRunner(self.app)
        await runner.setup()
            
        # Use SSL if available
        if ssl_context and os.environ.get('ENABLE_TLS', 'false').lower() == 'true':
            site = web.TCPSite(runner, self.host, self.port, ssl_context=ssl_context)
            protocol = "https"
        else:
            site = web.TCPSite(runner, self.host, self.port)
            protocol = "http"
            
        await site.start()
        
        logger.info(f"Server started at {protocol}://{self.host}:{self.port}")
        
        # Keep running until shutdown
        while self.running:
            await asyncio.sleep(1)
        
        # Cleanup
        await runner.cleanup()

async def main():
    """Main entry point"""
    server = SessionServer()
    await server.start()

if __name__ == '__main__':
    asyncio.run(main())