"""
Session service main server.
Coordinates all components and handles HTTP/WebSocket/SSE endpoints.
"""
import logging
import asyncio
import json
import time
import signal
import os
from typing import Dict, Any, Optional, List
import aiohttp_cors
from aiohttp import web

from source.config import config
from source.db.session_store import DatabaseManager
from source.api.clients.auth_client import AuthClient
from source.api.clients.exchange_client import ExchangeClient
from source.core.session_manager import SessionManager
from source.api.rest.routes import setup_rest_routes
from source.api.websocket.manager import WebSocketManager
from source.models.simulator import SimulatorStatus

# Import Redis for pub/sub if available
try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger('server')

class SessionServer:
    """Main session service server"""
    
    def __init__(self):
        """Initialize server components"""
        self.app = web.Application()
        self.running = False
        self.initialized = False
        self.shutdown_event = asyncio.Event()
    
    
    async def initialize(self):
        """Initialize all server components"""
        if self.initialized:
            return
        
        logger.info("Initializing server components")
        
        # Initialize Redis if available
        self.redis = None
        if REDIS_AVAILABLE:
            try:
                self.redis = await self._init_redis()
                logger.info("Redis connection established")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}")
                logger.warning("Continuing without Redis - some features will be limited")
        
        # Initialize database
        self.db_manager = DatabaseManager()
        await self.db_manager.connect()
        
        # Initialize API clients
        self.auth_client = AuthClient()
        self.exchange_client = ExchangeClient()
        
        # Initialize session manager
        self.session_manager = SessionManager(
            self.db_manager,
            self.auth_client,
            self.exchange_client,
            self.redis
        )
        
        # Start background tasks
        await self.session_manager.start_cleanup_task()
        
        # Initialize WebSocket manager
        self.websocket_manager = WebSocketManager(self.session_manager, self.redis)
        
        # Make components available in application context
        self.app['db_manager'] = self.db_manager
        self.app['auth_client'] = self.auth_client
        self.app['exchange_client'] = self.exchange_client
        self.app['session_manager'] = self.session_manager
        self.app['websocket_manager'] = self.websocket_manager

        # Add middleware for metrics and tracing
        from source.api.rest.handlers import metrics_middleware
        from source.utils.middleware import tracing_middleware

        self.app.middlewares.append(metrics_middleware)
        self.app.middlewares.append(tracing_middleware)

        # Set up routes
        setup_rest_routes(self.app)
        
        # Register WebSocket handler
        self.app.router.add_get('/ws', self.websocket_manager.handle_connection)
        
        # Add health check endpoints
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/readiness', self.readiness_check)
        self.app.router.add_get('/metrics', self.metrics_endpoint)  # Expose Prometheus metrics

        # Set up CORS
        self._setup_cors()
        
        # Set up signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
        
        self.initialized = True
        logger.info("Server initialization complete")

    # source/api/server.py (add to the class)
    async def metrics_endpoint(self, request):
        """Prometheus metrics endpoint"""
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

        metrics_data = generate_latest()
        return web.Response(
            body=metrics_data,
            content_type=CONTENT_TYPE_LATEST
        )

    async def _init_redis(self) -> aioredis.Redis:
        """Initialize Redis connection"""
        redis_client = aioredis.Redis(
            host=config.redis.host,
            port=config.redis.port,
            db=config.redis.db,
            password=config.redis.password,
            decode_responses=True
        )
        
        # Verify connection
        await redis_client.ping()
        
        # Register pod with Redis
        pod_info = {
            'name': config.kubernetes.pod_name,
            'host': config.server.host,
            'port': config.server.port,
            'started_at': time.time()
        }
        
        await redis_client.hset(f"pod:{config.kubernetes.pod_name}", mapping=pod_info)
        await redis_client.sadd("active_pods", config.kubernetes.pod_name)
        
        # Start Redis pubsub if needed
        self.pubsub_task = asyncio.create_task(self._run_pubsub(redis_client))
        
        return redis_client
    
    async def _run_pubsub(self, redis_client):
        """Process Redis pub/sub messages"""
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("session_events")
        
        try:
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    await self._handle_pubsub_message(message)
        except asyncio.CancelledError:
            await pubsub.unsubscribe("session_events")
            raise
    
    async def _handle_pubsub_message(self, message):
        """Handle Redis pub/sub message"""
        try:
            data = json.loads(message['data'])
            event_type = data.get('type')
            
            # Skip messages from this pod
            if data.get('pod_name') == config.kubernetes.pod_name:
                return
            
            logger.debug(f"Received pub/sub event: {event_type}")
            
            # Handle specific events
            if event_type == 'session_created':
                # Another pod created a session - nothing to do
                pass
            elif event_type == 'session_ended':
                # Another pod ended a session - nothing to do
                pass
            elif event_type == 'simulator_started':
                # Another pod started a simulator - notify WebSocket clients if we have any
                session_id = data.get('session_id')
                simulator_id = data.get('simulator_id')
                
                if session_id and self.websocket_manager:
                    await self.websocket_manager.broadcast_to_session(session_id, {
                        'type': 'simulator_update',
                        'status': 'STARTING',
                        'simulator_id': simulator_id
                    })
            elif event_type == 'simulator_stopped':
                # Another pod stopped a simulator - notify WebSocket clients if we have any
                session_id = data.get('session_id')
                simulator_id = data.get('simulator_id')
                
                if session_id and self.websocket_manager:
                    await self.websocket_manager.broadcast_to_session(session_id, {
                        'type': 'simulator_update',
                        'status': 'STOPPED',
                        'simulator_id': simulator_id
                    })
            elif event_type == 'pod_offline':
                # Another pod went offline - check for orphaned sessions
                # This would involve more complex logic to take over sessions
                pass
        except Exception as e:
            logger.error(f"Error handling pub/sub message: {e}")
    
    def _setup_cors(self):
        """Set up CORS for API endpoints"""
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
            )
        })
        
        # Apply CORS to all routes except WebSocket and SSE
        for route in list(self.app.router.routes()):
            path = route.resource.canonical
            if not (path == '/ws' or path == '/stream'):
                cors.add(route)
    
    async def health_check(self, request):
        """Simple health check endpoint"""
        return web.json_response({
            'status': 'UP',
            'timestamp': time.time(),
            'pod': config.kubernetes.pod_name
        })
    
    async def readiness_check(self, request):
        """Comprehensive readiness check"""
        # Check all dependencies
        db_ready = await self.db_manager.check_connection()
        auth_ready = await self.auth_client.check_service()
        
        if db_ready and auth_ready:
            return web.json_response({
                'status': 'READY',
                'timestamp': time.time(),
                'pod': config.kubernetes.pod_name,
                'checks': {
                    'database': 'UP',
                    'auth_service': 'UP',
                    'redis': 'UP' if self.redis else 'NOT CONFIGURED'
                }
            })
        else:
            return web.json_response({
                'status': 'NOT READY',
                'timestamp': time.time(),
                'pod': config.kubernetes.pod_name,
                'checks': {
                    'database': 'UP' if db_ready else 'DOWN',
                    'auth_service': 'UP' if auth_ready else 'DOWN',
                    'redis': 'UP' if self.redis else 'NOT CONFIGURED'
                }
            }, status=503)
    
    async def start(self):
        """Start the server"""
        if not self.initialized:
            await self.initialize()
        
        host = config.server.host
        port = config.server.port
        
        # Start the application
        runner = web.AppRunner(self.app)
        await runner.setup()
        
        site = web.TCPSite(runner, host, port)
        await site.start()
        
        self.running = True
        logger.info(f"Server started at http://{host}:{port}")
    
    
    async def shutdown(self):
        """Gracefully shut down the server"""
        if not self.running:
            return
        
        logger.info("Shutting down server")
        self.running = False
        
        # Force cleanup of this pod's sessions
        await self._cleanup_pod_sessions()
        
        # Unregister pod from Redis
        if self.redis:
            try:
                await self.redis.srem("active_pods", config.kubernetes.pod_name)
                await self.redis.publish("session_events", json.dumps({
                    'type': 'pod_offline',
                    'pod_name': config.kubernetes.pod_name,
                    'timestamp': time.time()
                }))
            except Exception as e:
                logger.error(f"Error unregistering pod from Redis: {e}")
        
        # Cancel background tasks
        if hasattr(self, 'pubsub_task'):
            self.pubsub_task.cancel()
            try:
                await self.pubsub_task
            except asyncio.CancelledError:
                pass
        
        # Stop session manager tasks
        await self.session_manager.stop_cleanup_task()
        
        # Close WebSocket connections
        await self.websocket_manager.close_all_connections("Server shutting down")
        
        # Close API clients
        await self.auth_client.close()
        await self.exchange_client.close()
        
        # Close Redis connection
        if self.redis:
            await self.redis.close()
        
        # Close database connection
        await self.db_manager.close()
        
        logger.info("Server shutdown complete")
        self.shutdown_event.set()

    async def _cleanup_pod_sessions(self):
        """Clean up sessions associated with this pod before shutdown"""
        try:
            # Get all sessions associated with this pod
            pod_sessions = await self.session_manager.db_manager.get_sessions_with_criteria({
                'pod_name': config.kubernetes.pod_name
            })
            
            if not pod_sessions:
                logger.info("No sessions to clean up for this pod")
                return
                
            logger.info(f"Cleaning up {len(pod_sessions)} sessions before pod termination")
            
            # Process simulators in parallel for faster shutdown
            simulator_tasks = []
            
            for session in pod_sessions:
                # Check if session has a simulator running
                if (hasattr(session.metadata, 'simulator_id') and 
                    session.metadata.simulator_id and 
                    hasattr(session.metadata, 'simulator_status') and
                    session.metadata.simulator_status != SimulatorStatus.STOPPED.value):
                    
                    simulator_id = session.metadata.simulator_id
                    simulator_endpoint = getattr(session.metadata, 'simulator_endpoint', None)
                    
                    # Create task to stop simulator
                    task = asyncio.create_task(
                        self._stop_simulator_with_fallbacks(
                            session.session_id, 
                            simulator_id, 
                            simulator_endpoint
                        )
                    )
                    simulator_tasks.append(task)
                    
                    # Update session metadata to indicate cleanup is in progress
                    await self.session_manager.db_manager.update_session_metadata(
                        session.session_id,
                        {
                            'simulator_status': 'STOPPING',
                            'cleanup_initiated_at': time.time()
                        }
                    )
            
            # Wait for simulator shutdowns with timeout
            if simulator_tasks:
                # Allow up to 10 seconds for graceful shutdowns
                done, pending = await asyncio.wait(
                    simulator_tasks, 
                    timeout=10.0,
                    return_when=asyncio.ALL_COMPLETED
                )
                
                # Cancel any pending tasks that didn't complete in time
                for task in pending:
                    task.cancel()
                    
                logger.info(f"Completed {len(done)}/{len(simulator_tasks)} simulator shutdowns")
                
                # For any pending/incomplete shutdowns, force K8s cleanup
                if pending:
                    for session in pod_sessions:
                        if hasattr(session.metadata, 'simulator_id') and session.metadata.simulator_id:
                            # Directly delete K8s resources as last resort
                            try:
                                await self.session_manager.k8s_client.delete_simulator_deployment(
                                    session.metadata.simulator_id
                                )
                                logger.info(f"Force deleted simulator {session.metadata.simulator_id} resources")
                            except Exception as e:
                                logger.error(f"Error force deleting simulator: {e}")
            
            # Update all session states to indicate cleanup
            for session in pod_sessions:
                # Mark the session for transfer to another pod
                await self.session_manager.db_manager.update_session_metadata(
                    session.session_id,
                    {
                        'pod_terminating': True,
                        'termination_time': time.time(),
                        'simulator_status': SimulatorStatus.STOPPED.value if hasattr(session.metadata, 'simulator_id') else None
                    }
                )
                
                # Notify clients via WebSocket that they should reconnect
                if self.websocket_manager:
                    await self.websocket_manager.broadcast_to_session(
                        session.session_id,
                        {
                            'type': 'pod_terminating', 
                            'message': 'Service instance is shutting down, please reconnect'
                        }
                    )
        
        except Exception as e:
            logger.error(f"Error cleaning up pod sessions: {e}")

    async def _stop_simulator_with_fallbacks(self, session_id, simulator_id, simulator_endpoint):
        """Stop simulator with multiple fallback strategies"""
        try:
            # Strategy 1: Try gRPC call if endpoint is available
            if simulator_endpoint:
                try:
                    result = await self.session_manager.exchange_client.stop_simulator(
                        simulator_endpoint, session_id
                    )
                    if result.get('success'):
                        logger.info(f"Successfully stopped simulator {simulator_id} via gRPC")
                        return True
                    else:
                        logger.warning(f"Failed to stop simulator {simulator_id} via gRPC: {result.get('error')}")
                except Exception as e:
                    logger.warning(f"Error calling stop_simulator via gRPC: {e}")
            
            # Strategy 2: Delete K8s resources directly
            try:
                await self.session_manager.k8s_client.delete_simulator_deployment(simulator_id)
                logger.info(f"Deleted simulator {simulator_id} K8s resources")
                return True
            except Exception as e:
                logger.error(f"Failed to delete simulator {simulator_id} K8s resources: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error in _stop_simulator_with_fallbacks: {e}")
            return False
        
    async def wait_for_shutdown(self):
        """Wait for server shutdown to complete"""
        await self.shutdown_event.wait()