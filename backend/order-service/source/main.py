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
from source.api.clients.session_client import SessionClient
from source.api.clients.exchange_client import ExchangeClient
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
    setup_tracing()
    logger.info("Distributed tracing initialized")

    # Initialize metrics
    setup_metrics()
    logger.info("Metrics collection initialized")

    # Resources to clean up on shutdown
    resources = {
        'runner': None,
        'order_repository': None,
        'auth_client': None,
        'session_client': None,
        'exchange_client': None
    }

    try:
        # Initialize database
        order_repository = OrderRepository()
        await order_repository.connect()
        resources['order_repository'] = order_repository

        # Initialize API clients
        auth_client = AuthClient(config.auth_service_url)
        session_client = SessionClient(config.session_service_url)
        exchange_client = ExchangeClient()
        resources['auth_client'] = auth_client
        resources['session_client'] = session_client
        resources['exchange_client'] = exchange_client

        # Initialize order manager
        order_manager = OrderManager(
            order_repository,
            auth_client,
            session_client,
            exchange_client
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
    if resources['order_repository']:
        logger.info("Closing database connection...")
        await resources['order_repository'].close()

    # Close auth client
    if resources['auth_client']:
        logger.info("Closing auth client...")
        await resources['auth_client'].close()

    # Close session client
    if resources['session_client']:
        logger.info("Closing session client...")
        await resources['session_client'].close()

    # Close exchange client
    if resources['exchange_client']:
        logger.info("Closing exchange client...")
        await resources['exchange_client'].close()

    logger.info("Server shutdown complete")


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        # This should not be reached now that we handle signals properly
        logger.info("Received keyboard interrupt")
        sys.exit(0)