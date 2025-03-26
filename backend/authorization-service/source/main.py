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
from source.utils.tracing import setup_tracing


# Logging setup function
def setup_logging():
    # Create logs directory if it doesn't exist
    log_dir = '/app/logs'

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
        maxBytes=10 * 1024 * 1024,  # 10 MB
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

    # Initialize distributed tracing
    setup_tracing()
    logger.info("Distributed tracing initialized")

    db_manager = None
    auth_manager = None
    runner = None

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

        # Keep the service running until stop event is signaled
        stop_event = asyncio.Event()

        # Set up signal handlers within the serve function
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop = asyncio.get_running_loop()
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(stop_event)))

        logger.info("Entering wait state - service ready")
        await stop_event.wait()
        logger.info("Stop event received, shutting down...")

    except Exception as e:
        logger.critical(f"Critical error during service startup: {e}")
        logger.critical(traceback.format_exc())
    finally:
        # Cleanup in reverse order
        logger.info("Performing service cleanup...")

        if auth_manager:
            logger.info("Stopping token cleanup thread...")
            auth_manager.stop_cleanup_thread()

        if runner:
            logger.info("Cleaning up web runner...")
            await runner.cleanup()

        if db_manager:
            logger.info("Closing database connections...")
            await db_manager.close()

        logger.info("Service cleanup completed")


async def shutdown(stop_event):
    """Graceful shutdown handler"""
    logger.info("Shutdown signal received, initiating graceful shutdown...")
    stop_event.set()


def main():
    """Entry point for the application"""
    logger.info("Starting authentication service main method")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(serve())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.critical(f"Unrecoverable error in main method: {e}")
        logger.critical(traceback.format_exc())
    finally:
        # Give pending tasks a moment to complete
        pending = asyncio.all_tasks(loop)
        for task in pending:
            if not task.done():
                try:
                    # Allow 5 seconds for tasks to complete
                    loop.run_until_complete(asyncio.wait_for(task, 5.0))
                except asyncio.TimeoutError:
                    logger.warning(f"Task did not complete during shutdown: {task}")
                except Exception as e:
                    logger.error(f"Error while shutting down task: {e}")

        logger.info("Closing event loop")
        loop.close()
        logger.info("Event loop closed")


if __name__ == '__main__':
    main()