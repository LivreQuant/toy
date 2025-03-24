#!/usr/bin/env python3
import os
import signal
import asyncio
import logging
import time
from aiohttp import web
import grpc
import importlib

from source.utils.logging_setup import setup_logging
from source.utils.config import config
from source.core.exchange_simulator import ExchangeSimulator
from source.api.grpc.service import ExchangeSimulatorService
from source.api.health.endpoints import health_check, readiness_check, metrics_endpoint

# Dynamically import generated protocol buffer modules
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import exchange_simulator_pb2_grpc

logger = logging.getLogger(__name__)

class Server:
    """Main server class"""
    
    def __init__(self):
        """Initialize server"""
        self.simulator = None
        self.grpc_server = None
        self.web_server = None
        self.running = False
        self.shutdown_event = asyncio.Event()
        self.start_time = time.time()
    
    async def setup(self):
        """Set up server components"""
        logger.info("Setting up exchange simulator server")
        
        # Create simulator
        self.simulator = ExchangeSimulator()
        
        # Set up gRPC server
        self.grpc_server = grpc.aio.server(
            options=[
                ('grpc.max_send_message_length', 10 * 1024 * 1024),
                ('grpc.max_receive_message_length', 10 * 1024 * 1024),
                ('grpc.keepalive_time_ms', 10000),
                ('grpc.keepalive_timeout_ms', 5000),
                ('grpc.keepalive_permit_without_calls', 1)
            ]
        )
        
        # Add service to gRPC server
        servicer = ExchangeSimulatorService(self.simulator)
        exchange_simulator_pb2_grpc.add_ExchangeSimulatorServicer_to_server(servicer, self.grpc_server)
        
        # Add gRPC port
        grpc_address = f"{config.host}:{config.port}"
        self.grpc_server.add_insecure_port(grpc_address)
        
        # Set up HTTP server for health checks
        app = web.Application()
        app['simulator'] = self.simulator
        app['start_time'] = self.start_time
        
        # Add routes
        app.router.add_get('/health', health_check)
        app.router.add_get('/readiness', readiness_check)
        app.router.add_get('/metrics', metrics_endpoint)
        
        # Start HTTP server
        self.web_runner = web.AppRunner(app)
        await self.web_runner.setup()
        
        # Use a different port for HTTP
        http_port = config.port + 1  # Use next port for HTTP
        http_site = web.TCPSite(self.web_runner, config.host, http_port)
        await http_site.start()
        logger.info(f"HTTP server started on {config.host}:{http_port}")
    
    async def start(self):
        """Start the server"""
        if self.running:
            return
        
        # Start gRPC server
        await self.grpc_server.start()
        logger.info(f"gRPC server started on {config.host}:{config.port}")
        
        self.running = True
    
    async def stop(self):
        """Stop the server"""
        if not self.running:
            return
        
        logger.info("Shutting down server...")
        self.running = False
        
        # Shutdown simulator
        if self.simulator:
            self.simulator.shutdown()
        
        # Shutdown gRPC server
        if self.grpc_server:
            await self.grpc_server.stop(5)  # 5 seconds grace
        
        # Shutdown HTTP server
        if hasattr(self, 'web_runner'):
            await self.web_runner.cleanup()
        
        logger.info("Server shutdown complete")
        self.shutdown_event.set()
    
    async def wait_for_termination(self):
        """Wait for server to terminate"""
        if self.grpc_server:
            await self.grpc_server.wait_for_termination()

async def main():
    """Main entry point"""
    # Set up logging
    setup_logging()
    
    # Create server
    server = Server()
    
    # Set up signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig, lambda: asyncio.create_task(server.stop())
        )
    
    try:
        # Set up and start server
        await server.setup()
        await server.start()
        
        # Wait for termination
        await server.wait_for_termination()
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        await server.stop()
        return 1
    
    return 0

if __name__ == "__main__":
    asyncio.run(main())