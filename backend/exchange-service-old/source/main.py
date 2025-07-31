# source/main.py - Enhanced with status reporting

import asyncio
import logging
import grpc
from concurrent import futures

from source.config import config

from source.utils.logging import setup_logging
from source.utils.metrics import setup_metrics
from source.utils.tracing import setup_tracing

from source.core.exchange_manager import ExchangeManager

from source.api.service import ExchangeSimulatorService

from source.api.grpc.session_exchange_interface_pb2_grpc import add_SessionExchangeSimulatorServicer_to_server
from source.api.grpc.conviction_exchange_interface_pb2_grpc import add_ConvictionExchangeSimulatorServicer_to_server

logger = logging.getLogger('exchange_simulator')


class ExchangeSimulator:
    def __init__(self):
        self.exchange_manager = None
        self.grpc_server = None
        self.health_service = None

    async def initialize_exchange(self):
        """
        Initialize the exchange for the specific user
        This method sets up all necessary components for the exchange
        """
        try:
            # Validate and extract essential configuration
            user_id = config.simulator.user_id
            desk_id = config.simulator.desk_id

            if not user_id:
                raise ValueError("User ID is required to initialize exchange")

            # Create Exchange Manager
            self.exchange_manager = ExchangeManager(
                user_id=user_id,
                desk_id=desk_id
            )

            # Create health service first (so it can track initialization)
            self.health_service = self.exchange_manager.get_health_service() if hasattr(self.exchange_manager, 'get_health_service') else None

            # Perform initial setup with status reporting
            await self.exchange_manager.initialize()

            logger.info(f"Exchange initialized for User ID: {user_id}")
            logger.info(f"Desk ID: {desk_id}")

            return self.exchange_manager

        except Exception as e:
            logger.error(f"Failed to initialize exchange: {e}")
            raise

    async def create_grpc_server(self):
        """Create and configure gRPC server"""
        if not self.exchange_manager:
            raise RuntimeError("Exchange manager must be initialized first")

        self.grpc_server = grpc.aio.server(
            futures.ThreadPoolExecutor(max_workers=10),
            options=[
                ('grpc.max_send_message_length', 100 * 1024 * 1024),
                ('grpc.max_receive_message_length', 100 * 1024 * 1024),
            ]
        )

        # Create and add service
        self.simulator_service = ExchangeSimulatorService(self.exchange_manager)
        add_SessionExchangeSimulatorServicer_to_server(self.simulator_service, self.grpc_server)
        add_ConvictionExchangeSimulatorServicer_to_server(self.simulator_service, self.grpc_server)

        # Bind server to port
        listen_addr = f'{config.server.host}:{config.server.grpc_port}'
        self.grpc_server.add_insecure_port(listen_addr)

        # Mark gRPC server as ready
        if self.health_service:
            self.health_service.mark_service_ready('grpc_server', True)

        return self.grpc_server, listen_addr

    async def setup_observability(self):
        """Setup tracing and metrics"""
        if config.tracing.enabled:
            setup_tracing()
        if config.metrics.enabled:
            setup_metrics()

    async def start(self):
        """
        Full startup sequence for the exchange simulator with status reporting
        """
        try:
            # Setup logging
            setup_logging()
            logger.info("Starting Exchange Simulator")

            # Setup observability
            await self.setup_observability()

            # Initialize exchange (this will create health service internally)
            await self.initialize_exchange()

            # Create gRPC server
            server, listen_addr = await self.create_grpc_server()

            # Start HTTP health server
            await self.simulator_service.start_health_service()
            
            # Start gRPC server
            await server.start()
            logger.info(f"gRPC Exchange Simulator started on {listen_addr}")

            # Mark all initialization as complete
            if hasattr(self.simulator_service, 'health_service'):
                # Final health check to mark as fully ready
                await asyncio.sleep(1)  # Brief delay to ensure everything is settled
                logger.info("Exchange Simulator fully operational and ready for connections")

            # Keep server running
            await server.wait_for_termination()

        except Exception as e:
            logger.error(f"Failed to start Exchange Simulator: {e}")
            raise

    async def stop(self):
        """Gracefully stop the exchange and server"""
        try:
            if hasattr(self, 'simulator_service') and self.simulator_service:
                await self.simulator_service.stop_health_service()
                
            if self.grpc_server:
                await self.grpc_server.stop(0)

            if self.exchange_manager:
                await self.exchange_manager.cleanup()

            logger.info("Exchange Simulator stopped successfully")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


async def main():
    simulator = ExchangeSimulator()

    try:
        await simulator.start()
    except KeyboardInterrupt:
        logger.info("Exchange Simulator interrupted by user")
        await simulator.stop()
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        await simulator.stop()


if __name__ == "__main__":
    asyncio.run(main())