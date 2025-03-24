import logging
import asyncio
import grpc
from concurrent import futures
import time

from source.utils.config import Config
from source.simulator.exchange_simulator import ExchangeSimulator
from source.api.grpc_service import ExchangeSimulatorService

import exchange_simulator_pb2_grpc

logger = logging.getLogger(__name__)

class GrpcServer:
    def __init__(self):
        self.simulator = ExchangeSimulator()
        self.server = None
        self.running = False
        self.shutdown_event = asyncio.Event()
    
    async def start(self):
        """Start the gRPC server"""
        # Create gRPC server
        self.server = grpc.aio.server(
            futures.ThreadPoolExecutor(max_workers=Config.MAX_WORKER_THREADS),
            options=[
                ('grpc.max_send_message_length', 10 * 1024 * 1024),
                ('grpc.max_receive_message_length', 10 * 1024 * 1024),
                ('grpc.keepalive_time_ms', 10000),
                ('grpc.keepalive_timeout_ms', 5000),
                ('grpc.keepalive_permit_without_calls', 1)
            ]
        )
        
        # Register service
        service = ExchangeSimulatorService(self.simulator)
        exchange_simulator_pb2_grpc.add_ExchangeSimulatorServicer_to_server(service, self.server)
        
        # Add port
        address = f"{Config.HOST}:{Config.PORT}"
        self.server.add_insecure_port(address)
        
        # Start server
        await self.server.start()
        self.running = True
        logger.info(f"gRPC server started on {address}")
    
    async def shutdown(self):
        """Shutdown the server gracefully"""
        if not self.running:
            return
        
        logger.info("Shutting down gRPC server...")
        
        # Stop simulator
        self.simulator.shutdown()
        
        # Stop server
        if self.server:
            # Grace period for existing calls
            await self.server.stop(grace=5.0)
            self.server = None
        
        self.running = False
        self.shutdown_event.set()
        logger.info("gRPC server stopped")
    
    async def wait_for_termination(self):
        """Wait for server termination"""
        await self.shutdown_event.wait()