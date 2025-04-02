import asyncio
import logging
import signal
import sys
import time
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
from source.api.grpc.exchange_simulator_pb2_grpc import add_ExchangeSimulatorServicer_to_server

logger = logging.getLogger('exchange_simulator')

class ExchangeServer:
    def __init__(self):
        # Initialize core components
        self.market_data = MarketDataGenerator()
        self.order_manager = OrderManager(self.market_data)
        self.portfolio_manager = PortfolioManager()

        # Track last heartbeat time from session service
        self.last_session_heartbeat = time.time()
        self.session_ttl = int(os.environ.get('SESSION_TTL_SECONDS', '120'))  # 2 minutes default
        
        # Initialize gRPC server
        self.grpc_server = None
        self.running = False
        self.ttl_monitor_task = None

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
        
        # Give service a reference to this server for heartbeat tracking
        simulator_service.server = self

        # Add service to server
        add_ExchangeSimulatorServicer_to_server(
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
        
        # Start TTL monitor
        self.ttl_monitor_task = asyncio.create_task(self._monitor_session_ttl())

    async def stop(self):
        """Gracefully stop the server"""
        if self.grpc_server:
            logger.info("Shutting down gRPC server...")
            await self.grpc_server.stop(0)
            self.running = False

    
    async def _monitor_session_ttl(self):
        """Monitor session TTL and self-terminate if no heartbeats received"""
        logger.info(f"Starting session TTL monitor with TTL={self.session_ttl}s")
        
        while self.running:
            try:
                await asyncio.sleep(5)  # Check every 5 seconds
                
                # Calculate time since last heartbeat
                time_since_heartbeat = time.time() - self.last_session_heartbeat
                
                # If we exceed TTL, shut down
                if time_since_heartbeat > self.session_ttl:
                    logger.warning(
                        f"No heartbeat received from session service for {time_since_heartbeat:.1f}s "
                        f"(TTL: {self.session_ttl}s). Self-terminating!"
                    )
                        
                    # Update database directly
                    session_id = os.environ.get('SESSION_ID')
                    simulator_id = os.environ.get('SIMULATOR_ID')
                        
                    if session_id and simulator_id:
                        try:
                            # Create database manager if not exists
                            if not hasattr(self, 'db_manager'):
                                from source.db.database import DatabaseManager
                                self.db_manager = DatabaseManager()
                                await self.db_manager.connect()
                            
                            # Update database
                            await self.db_manager.update_simulator_stopped(
                                session_id, 
                                simulator_id, 
                                reason=f"TTL exceeded: No heartbeat for {time_since_heartbeat:.1f}s"
                            )
                        except Exception as e:
                            logger.error(f"Failed to update database before self-termination: {e}")
                    
                    # Shut down gracefully
                    await self.stop()
                    
                    # Exit with error code to signal Kubernetes
                    logger.info("Exiting process due to session TTL expiration")
                    sys.exit(1)
                
                # Log warning if approaching TTL
                elif time_since_heartbeat > (self.session_ttl * 0.8):
                    logger.warning(
                        f"No heartbeat received for {time_since_heartbeat:.1f}s. "
                        f"Will terminate in {self.session_ttl - time_since_heartbeat:.1f}s"
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in session TTL monitor: {e}")

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