#!/usr/bin/env python3
import asyncio
import logging
import os
import signal
import socket
from aiohttp import web
import aiohttp_cors

# Import API components
from api.routes import setup_routes
from api.handlers import (
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
from session.manager import SessionManager
from session.state import SessionState, SessionStatus, SimulatorStatus

# Import gRPC clients
from grpc.exchange import ExchangeServiceClient
from grpc.auth import AuthServiceClient

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
    
    async def init_components(self):
        """Initialize all service components"""
        # Database connection
        self.db_manager = DatabaseManager()
        await self.db_manager.connect()
        
        # gRPC clients
        self.auth_client = AuthServiceClient()
        await self.auth_client.connect()
        
        self.exchange_client = ExchangeServiceClient()
        
        # Session manager
        self.session_manager = SessionManager(
            self.db_manager, 
            self.auth_client,
            self.exchange_client,
            pod_name=self.pod_name
        )
        
        # SSE adapter
        self.sse_adapter = SSEAdapter(self.exchange_client)
        
        # WebSocket protocol handler
        self.ws_protocol = WebSocketProtocol(self.session_manager)
        
        # WebSocket manager
        self.websocket_manager = WebSocketManager(
            self.session_manager,
            self.ws_protocol
        )
        
        # Store components in app for access in request handlers
        self.app['db_manager'] = self.db_manager
        self.app['session_manager'] = self.session_manager
        self.app['websocket_manager'] = self.websocket_manager
        self.app['auth_client'] = self.auth_client
        self.app['exchange_client'] = self.exchange_client
        self.app['sse_adapter'] = self.sse_adapter
    
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
        return web.Response(text="OK", status=200)
    
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
    
    async def start(self):
        """Initialize and start the server"""
        # Setup signal handlers
        self.setup_signal_handlers()
        
        # Initialize components
        await self.init_components()
        
        # Setup routes and middleware
        self.setup_routes()
        self.setup_cors()
        
        # Start the server
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        logger.info(f"Server started at http://{self.host}:{self.port}")
        
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