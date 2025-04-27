# src/main.py
import asyncio
import logging
import os
import signal
import sys
from datetime import datetime

from src.config import config
from src.utils.logging_utils import setup_logging
from src.generator.market_data_generator import MarketDataGenerator
from src.distributor.market_data_distributor import MarketDataDistributor
from src.api.registration_service import RegistrationService


async def shutdown(distributor, api_service):
    """Gracefully shut down all services"""
    logging.info("Shutting down market data distributor service...")
    
    # Stop the API service first
    if api_service:
        await api_service.shutdown()
    
    # Then stop the distributor
    if distributor:
        await distributor.stop()
    
    logging.info("Shutdown complete")


async def main():
    """Main entry point for the application"""
    # Setup logging
    logger = setup_logging()
    logger.info("Starting market data distributor service")
    
    try:
        # Create the market data generator with configured symbols
        generator = MarketDataGenerator(config.SYMBOLS)
        
        # Create the distributor
        distributor = MarketDataDistributor(
            generator=generator,
            update_interval=config.UPDATE_INTERVAL
        )
        
        # Create the API service
        api_service = RegistrationService(
            distributor=distributor,
            host=config.API_HOST,
            port=config.API_PORT
        )
        
        # Set up shutdown handler
        loop = asyncio.get_running_loop()
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(shutdown(distributor, api_service))
            )
        
        # Start the API service
        await api_service.setup()
        
        # Start the distributor
        await distributor.start()
        
        # Keep the program running
        while True:
            await asyncio.sleep(60)  # Check every minute if we need to stop
            
            # Check if we're outside operating hours
            current_hour = datetime.now().hour
            if current_hour < config.STARTUP_HOUR or current_hour >= config.SHUTDOWN_HOUR:
                logger.info("Outside operating hours, service will continue running but data distribution is paused")
    
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
    finally:
        await shutdown(distributor, api_service)


if __name__ == "__main__":
    asyncio.run(main())