# source/main.py
import asyncio
import logging
import logging.handlers
import os
import signal
import sys
import traceback
from aiohttp import web

from source.core.auth_manager import AuthManager
from source.db.db_manager import DatabaseManager
from source.api.rest_routes import setup_rest_app

# Logging setup function
def setup_logging():
    # Create logs directory if it doesn't exist
    log_dir = '/home/samaral/projects/toy/20250325/backend/authorization-service'
    #log_dir = '/app/logs'

    os.makedirs(log_dir, exist_ok=True)
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', 'DEBUG')))

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    ))
    logger.addHandler(console_handler)

    # Rotating File handler
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'auth_service.log'),
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=5
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    ))
    logger.addHandler(file_handler)

    return logging.getLogger('auth_service')

# Configure logger
logger = setup_logging()

async def serve():
    """Main service startup and run method"""
    logger.info("Starting authentication service")
    
    try:
        # Create database manager
        db_manager = DatabaseManager()
        await db_manager.connect()
        logger.info("Database manager connected successfully")

        # Create auth manager
        auth_manager = AuthManager(db_manager)
        logger.info("Authentication manager initialized")

        # Set up REST API server
        app = setup_rest_app(auth_manager)
        rest_port = int(os.getenv('REST_PORT', '8001'))

        # Create web runner
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', rest_port)
        await site.start()

        logger.info(f"REST Auth service started on port {rest_port}")

        # Keep the service running indefinitely
        try:
            # Log start of indefinite wait
            logger.info("Entering indefinite wait state")
            
            # Use asyncio.Event to keep the service running
            stop_event = asyncio.Event()
            await stop_event.wait()
        
        except asyncio.CancelledError:
            logger.warning("Service wait state was cancelled")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in serve method: {e}")
            logger.error(traceback.format_exc())
            raise
        finally:
            # Cleanup
            logger.info("Initiating service cleanup")
            await runner.cleanup()
            await db_manager.close()
            logger.info("Service cleanup completed")

    except Exception as e:
        logger.critical(f"Critical error during service startup: {e}")
        logger.critical(traceback.format_exc())
        raise

def main():
    """Entry point for the application"""
    logger.info("Starting authentication service main method")
    
    loop = asyncio.get_event_loop()
    
    # Enhance error handling in event loop
    def exception_handler(loop, context):
        # Log any unhandled exceptions in the event loop
        exception = context.get('exception')
        logger.error(f"Unhandled exception in event loop: {context}")
        if exception:
            logger.error(f"Exception details: {exception}")
            logger.error(traceback.format_exc())

    loop.set_exception_handler(exception_handler)
    
    # Create a shutdown event
    shutdown_event = asyncio.Event()
    
    # Setup signal handlers for graceful shutdown
    def signal_handler():
        logger.info("Received shutdown signal")
        shutdown_event.set()
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig, 
            signal_handler
        )

    try:
        # Run the service
        logger.info("Running service in event loop")
        loop.run_until_complete(serve())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
    except Exception as e:
        logger.critical(f"Unrecoverable error in main method: {e}")
        logger.critical(traceback.format_exc())
    finally:
        logger.info("Closing event loop")
        loop.close()
        logger.info("Event loop closed")

if __name__ == '__main__':
    main()