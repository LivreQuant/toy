#!/usr/bin/env python3
"""
Main entry point for the Session Service.
Initializes and starts the server with proper signal handling and graceful shutdown.
"""
import asyncio
import logging
import signal
import uvloop
import sys

from source.config import config

from source.utils.logging import setup_logging
from source.utils.tracing import setup_tracing
from source.utils.metrics import setup_metrics

from source.server import SessionServer

logger = logging.getLogger('session_service')


async def main():
    """Initialize and run the session service"""
    # Setup logging
    setup_logging()

    logger.info("Starting session service")

    # Initialize tracing
    if config.tracing.enabled:
        logger.info("Initializing distributed tracing")
        setup_tracing()

    # Initialize metrics
    if config.metrics.enabled:
        logger.info("Initializing metrics collection")
        setup_metrics(config.metrics.port)

    # Create server instance
    server = SessionServer()

    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(server.shutdown()))

    # Initialize server components with proper error handling
    try:
        await server.initialize()
    except Exception as init_error:
        logger.error(f"Server initialization failed: {init_error}")
        return 1

    # Start server with error handling
    try:
        await server.start()
    except Exception as start_error:
        logger.error(f"Failed to start server: {start_error}")
        return 1

    # Run until shutdown is complete
    try:
        await server.wait_for_shutdown()
    except Exception as e:
        logger.error(f"Error during server execution: {e}")
        return 1

    logger.info("Server shutdown complete")
    return 0


if __name__ == "__main__":
    try:
        # Use uvloop for better performance if available
        try:
            uvloop.install()
            logger.info("Using uvloop for asyncio")
        except ImportError:
            logger.info("uvloop not available, using standard asyncio")

        # Run main async function
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        sys.exit(0)