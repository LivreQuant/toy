# main.py
import asyncio
import logging
import os
import signal
from aiohttp import web

from source.core.auth_manager import AuthManager
from source.db.database import DatabaseManager
from source.api.rest_routes import setup_rest_app

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('auth_service')

async def serve():
    # Create database manager
    db_manager = DatabaseManager()
    await db_manager.connect()
    
    # Create auth manager
    auth_manager = AuthManager(db_manager)
    
    # Set up REST API server
    app = setup_rest_app(auth_manager)
    rest_port = int(os.getenv('REST_PORT', '8000'))
    
    # Configure signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(runner, db_manager)))
    
    # Start REST server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', rest_port)
    await site.start()
    
    logger.info(f"REST Auth service started on port {rest_port}")
    
    # Keep running until signaled to stop
    while True:
        await asyncio.sleep(3600)  # Just to keep the event loop running

async def shutdown(runner, db_manager):
    logger.info("Shutting down server...")
    
    # Shutdown REST server
    await runner.cleanup()
    
    # Close database connections
    await db_manager.close()
    
    logger.info("Server shutdown complete")
    asyncio.get_event_loop().stop()

if __name__ == '__main__':
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")