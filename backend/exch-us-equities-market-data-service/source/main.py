# source/main.py
import asyncio
import logging
import signal
import grpc
import sys
import os

from source.config import config
from source.utils.logging_utils import setup_logging
from source.generator.market_data_generator import ControlledMarketDataGenerator
from source.db.database import DatabaseManager
from source.api.grpc.market_exchange_interface_pb2_grpc import add_MarketDataServiceServicer_to_server
from source.service.market_data_service import MarketDataService
from source.service.health import HealthService

async def shutdown(service, server, health_service):
    """Gracefully shut down all services"""
    logging.info("Shutting down market data service...")
    
    # Stop the service first
    if service:
        await service.stop()
    
    # Stop the health service
    if health_service:
        await health_service.shutdown()

    # Then stop the server
    if server:
        await server.stop(5)  # 5 seconds grace period
    
    logging.info("Shutdown complete")

async def main():
    """Main entry point for the controlled market data service"""
    # Setup logging
    logger = setup_logging()
    logger.info("Starting controlled market data service")
    
    try:
        # Load market configuration from JSON
        market_config = config.load_market_config()
        logger.info(f"Loaded market config: {market_config['config_name']}")
        
        # Create the controlled market data generator
        generator = ControlledMarketDataGenerator(market_config)
        
        # Create database manager
        db_manager = DatabaseManager()
        
        # Create the service with configurable update interval
        update_interval = market_config.get("time_increment_minutes", 1) * 60  # Convert to seconds
        service = MarketDataService(
            generator=generator,
            db_manager=db_manager,
            update_interval=update_interval
        )
                
        health_service = HealthService(http_port=50061)
        await health_service.setup()

        # Create gRPC server
        server = grpc.aio.server()
        add_MarketDataServiceServicer_to_server(service, server)
        
        # Start server
        server_addr = f"{config.API_HOST}:{config.API_PORT}"
        server.add_insecure_port(server_addr)
        await server.start()
        
        logger.info(f"Controlled market data server started on {server_addr}")
        logger.info(f"Market timezone: {market_config.get('timezone', 'UTC')}")
        logger.info(f"Update interval: {update_interval} seconds")
        
        # Set up shutdown handler
        loop = asyncio.get_running_loop()
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(shutdown(service, server, health_service))
            )
        
        # Start the service
        await service.start()
        
        # Keep the server running
        await server.wait_for_termination()
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
    finally:
        await shutdown(service if 'service' in locals() else None, 
                       server if 'server' in locals() else None, 
                       health_service if 'health_service' in locals() else None)

if __name__ == "__main__":
    asyncio.run(main())