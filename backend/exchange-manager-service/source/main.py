#!/usr/bin/env python3
import os
import signal
import asyncio
import logging

from source.config import Config
from source.utils.logging_setup import setup_logging
from source.utils.grpc_server import GrpcServer

logger = logging.getLogger(__name__)

async def main():
    # Set up logging
    setup_logging()
    
    # Initialize server
    server = GrpcServer()
    
    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(server.shutdown()))
    
    # Start server
    await server.start()
    
    # Keep running until shutdown
    await server.wait_for_termination()

if __name__ == "__main__":
    asyncio.run(main())