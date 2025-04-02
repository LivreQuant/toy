import asyncio
import logging
import signal
import sys
import grpc
import os
from concurrent import futures

from source.config import config
from source.utils.logging import setup_logging
from source.utils.metrics import setup_metrics
from source.utils.tracing import setup_tracing

from source.core.market_data import MarketDataGenerator
from source.core.order_manager import OrderManager
from source.core.portfolio_manager import PortfolioManager

from source.api.grpc.service import ExchangeSimulatorService
import exchange_simulator_pb2_grpc

logger = logging.getLogger('exchange_simulator')

class ExchangeServer:
    def __init__(self):
        # Initialize core components
        self.market_data = MarketDataGenerator()
        self.order_manager = OrderManager(self.market_data)
        self.portfolio_manager = PortfolioManager()

        # Initialize gRPC server
        self.grpc_server = None
        self.running = False

    async def start(self):
        """Start the gRPC server"""
        # Create gRPC server
        self.grpc_server = grpc.aio.server(
            futures.ThreadPoolExecutor(max_workers=10),
            options=[
                ('grpc.max_send_message_length', 100 * 1024 * 1024),
                ('grpc.max_receive_message_length', 100 * 1024 * 1024),
            ]
        )

        # Create service
        simulator_service = ExchangeSimulatorService(
            self.market_data, 
            self.order_manager, 
            self.portfolio_manager
        )

        # Add service to server
        exchange_simulator_pb2_grpc.add_ExchangeSimulatorServicer_to_server(
            simulator_service, 
            self.grpc_server
        )

        # Bind server to port
        listen_addr = f'{config.server.host}:{config.server.grpc_port}'
        self.grpc_server.add_insecure_port(listen_addr)

        # Start server
        await self.grpc_server.start()
        self.running = True
        logger.info(f"gRPC server started on {listen_addr}")

    async def stop(self):
        """Gracefully stop the server"""
        if self.grpc_server:
            logger.info("Shutting down gRPC server...")
            await self.grpc_server.stop(0)
            self.running = False

async def main():
    # Setup logging
    setup_logging()
    logger.info("Starting Exchange Simulator")

    # Setup tracing
    if config.tracing.enabled:
        setup_tracing()

    # Setup metrics
    if config.metrics.enabled:
        setup_metrics()

    # Create server
    server = ExchangeServer()

    # Setup signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig, lambda: asyncio.create_task(server.stop())
        )

    try:
        # Start server
        await server.start()

        # Keep server running
        while server.running:
            await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        await server.stop()

if __name__ == "__main__":
    try:
        # Use uvloop if available for better performance
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ImportError:
        pass

    asyncio.run(main())