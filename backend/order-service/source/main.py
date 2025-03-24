#!/usr/bin/env python3
import asyncio
import logging
import signal
import sys
import os

from source.utils.logging import setup_logging
from source.api.rest.routes import setup_app
from source.config import config
from source.db.order_repository import OrderRepository
from source.api.clients.auth_client import AuthClient
from source.api.clients.exchange_client import ExchangeClient
from source.utils.redis_client import RedisClient
from source.core.order_manager import OrderManager

logger = logging.getLogger('order_service')

async def main():
    """Initialize and run the order service"""
    # Setup logging
    setup_logging()
    
    logger.info("Starting order service")
    
    try:
        # Initialize Redis client
        redis_client = await RedisClient.create()
        
        # Initialize database
        order_repository = OrderRepository()
        await order_repository.connect()
        
        # Initialize API clients
        auth_client = AuthClient(config.auth_service_url)
        exchange_client = ExchangeClient(redis_client)
        
        # Initialize order manager
        order_manager = OrderManager(
            order_repository, 
            auth_client, 
            exchange_client, 
            redis_client
        )
        
        # Setup and start REST API
        app, runner, site = await setup_app(order_manager)
        
        # Configure signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig, 
                lambda: asyncio.create_task(shutdown(runner, order_repository, auth_client, exchange_client, redis_client))
            )
        
        logger.info(f"Order service started on port {config.rest_port}")
        
        # Keep running until signaled to stop
        while True:
            await asyncio.sleep(3600)  # Just to keep the event loop running
    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        return 1
    
    return 0

async def shutdown(runner, order_repository, auth_client, exchange_client, redis_client):
    logger.info("Shutting down server gracefully...")

    # Shutdown REST server
    await runner.cleanup()

    # Close connections
    logger.info("Closing database connection...")
    await order_repository.close()

    logger.info("Closing auth client...")
    await auth_client.close()

    logger.info("Closing exchange client...")
    await exchange_client.close()

    logger.info("Closing Redis connection...")
    await redis_client.close()

    logger.info("Server shutdown complete")
    asyncio.get_event_loop().stop()

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        sys.exit(0)