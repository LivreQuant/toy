# source/main.py
import asyncio
import logging
import signal
import sys

from source.utils.logging import setup_logging
from source.api.rest.routes import setup_app
from source.config import config
from source.db.connection_pool import DatabasePool
from source.db.order_repository import OrderRepository
from source.core.state_manager import StateManager  # Import StateManager
from source.clients.auth_client import AuthClient
from source.clients.exchange_client import ExchangeClient
from source.core.order_manager import OrderManager
from source.utils.metrics import setup_metrics
from source.utils.tracing import setup_tracing

logger = logging.getLogger('order_service')


class GracefulExit(SystemExit):
    """Special exception for graceful exit"""
    pass


async def main():
    """Initialize and run the order service"""
    # Setup logging
    setup_logging()

    logger.info("Starting order service")

    # Initialize tracing
    if config.enable_tracing:
        setup_tracing()
        logger.info("Distributed tracing initialized")

    # Initialize metrics
    if config.enable_metrics:
        setup_metrics()
        logger.info("Metrics collection initialized")

    # Resources to clean up on shutdown
    resources = {
        'runner': None,
        'db_pool': None,
        'order_repository': None,
        'auth_client': None,
        'exchange_client': None,
        'state_manager': None  # Add state manager to resources
    }

    try:
        # Initialize state manager
        state_manager = StateManager(timeout_seconds=30)  # Optional: Set timeout
        resources['state_manager'] = state_manager

        # Initialize database
        db_pool = DatabasePool()
        await db_pool.get_pool()  # Ensure connection is established
        resources['db_pool'] = db_pool

        # Initialize order repository
        order_repository = OrderRepository()
        resources['order_repository'] = order_repository

        # Initialize API clients
        auth_client = AuthClient(config.auth_service_url)
        exchange_client = ExchangeClient()
        resources['auth_client'] = auth_client
        resources['exchange_client'] = exchange_client

        # Initialize order manager
        order_manager = OrderManager(
            order_repository,
            auth_client,
            exchange_client,
            state_manager  # Pass the state manager
        )

        # Setup and start REST API
        app, runner, site = await setup_app(order_manager)
        resources['runner'] = runner

        # Set up signal handlers
        def handle_signal():
            raise GracefulExit()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, handle_signal)

        logger.info(f"Order service started on port {config.rest_port}")

        # Keep the service running until a signal is received
        while True:
            await asyncio.sleep(1)

    except GracefulExit:
        # Handle graceful exit
        pass
    except Exception as e:
        logger.error(f"Failed to start or run service: {e}")
        return 1
    finally:
        # Clean up resources
        await cleanup_resources(resources)

    return 0


async def cleanup_resources(resources):
    """Clean up all resources gracefully"""
    logger.info("Shutting down server gracefully...")

    # Shutdown REST server
    if resources['runner']:
        logger.info("Cleaning up web server...")
        await resources['runner'].cleanup()

    # Close database connection
    if resources['db_pool']:
        logger.info("Closing database connection...")
        await resources['db_pool'].close()

    # Close auth client
    if resources['auth_client']:
        logger.info("Closing auth client...")
        await resources['auth_client'].close()

    # Close exchange client
    if resources['exchange_client']:
        logger.info("Closing exchange client...")
        await resources['exchange_client'].close()

    # Additional cleanup for state manager if needed
    if resources.get('state_manager'):
        logger.info("Resetting state manager...")
        # Any additional cleanup logic for state manager

    logger.info("Server shutdown complete")


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        sys.exit(0)
