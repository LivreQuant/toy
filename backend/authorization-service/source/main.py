# source/main.py
import asyncio
import logging
import logging.handlers
import os
import signal
import sys
import traceback
from aiohttp import web

from source.db.db_manager import DatabaseManager
from source.core.auth_manager import AuthManager
from source.core.email_manager import EmailManager
from source.core.verification_manager import VerificationManager
from source.api.rest_routes import setup_rest_app
from source.utils.tracing import setup_tracing
from source.utils.metrics import setup_metrics


# Logging setup function
def setup_logging():
    """Configure application logging with environment-aware paths"""
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', 'DEBUG')))

    # Console handler (always enabled)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    ))
    logger.addHandler(console_handler)

    # Try to set up file logging if possible
    try:
        # Use an environment-appropriate directory
        if os.getenv('KUBERNETES_SERVICE_HOST'):
            # In Kubernetes, use /app/logs
            log_dir = '/app/logs'
        else:
            # Local development - use a directory in the project
            log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')

        os.makedirs(log_dir, exist_ok=True)

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
        logger.info(f"File logging enabled at {log_dir}")
    except Exception as e:
        logger.warning(f"Could not set up file logging: {e}. Continuing with console logging only.")

    return logging.getLogger('auth_service')


# Configure logger
logger = setup_logging()


async def serve():
    """Main service startup and run method"""
    logger.info("Starting authentication service")

    # Initialize distributed tracing
    setup_tracing()
    logger.info("Distributed tracing initialized")

    # Initialize metrics
    setup_metrics()
    logger.info("Metrics initialization completed")

    # Managers for dependency injection and cleanup
    managers = {}

    try:
        # Create and initialize database manager
        db_manager = DatabaseManager()
        await db_manager.connect()
        managers['db_manager'] = db_manager
        logger.info("Database manager connected successfully")

        # Create and initialize email manager (no database dependency)
        email_manager = EmailManager()
        await email_manager.initialize()
        managers['email_manager'] = email_manager
        logger.info("Email manager initialized")

        # Create and initialize verification manager
        verification_manager = VerificationManager(db_manager)
        await verification_manager.initialize()
        managers['verification_manager'] = verification_manager
        logger.info("Verification manager initialized")

        # Create and initialize auth manager with all dependencies
        auth_manager = AuthManager(db_manager)
        auth_manager.register_dependency('email_manager', email_manager)
        auth_manager.register_dependency('verification_manager', verification_manager)
        await auth_manager.initialize()
        managers['auth_manager'] = auth_manager
        logger.info("Auth manager initialized with dependencies")

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
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(stop_event, managers)))

        logger.info("Entering wait state - service ready")
        await stop_event.wait()
        logger.info("Stop event received, shutting down...")

    except Exception as e:
        logger.critical(f"Critical error during service startup: {e}")
        logger.critical(traceback.format_exc())
    finally:
        # Cleanup will be handled by the shutdown function
        pass


async def shutdown(stop_event, managers):
    """Graceful shutdown handler"""
    logger.info("Shutdown signal received, initiating graceful shutdown...")

    # Cleanup in reverse order of initialization (dependencies first)
    for name, manager in reversed(list(managers.items())):
        try:
            logger.info(f"Cleaning up {name}...")
            await manager.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up {name}: {e}")

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
