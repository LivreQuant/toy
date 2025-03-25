#!/usr/bin/env python3
"""
Main entry point for the Session Service.
Initializes and starts the server with proper signal handling and graceful shutdown.
"""
import asyncio
import logging
import signal
import sys
import os

from source.config import Config
from source.api.server import SessionServer
from source.utils.logging import setup_logging

logger = logging.getLogger('session_service')


async def main():
    """Initialize and run the session service"""
    # Setup logging
    setup_logging()

    logger.info("Starting session service")

    # Create server instance
    server = SessionServer()

    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig, lambda: asyncio.create_task(server.shutdown()))

    # Initialize server components
    try:
        await server.initialize()
        await server.start()
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
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
            import uvloop

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
