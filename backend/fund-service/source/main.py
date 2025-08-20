# source/main.py
import asyncio
import logging
import signal
import sys

from source.utils.logging import setup_logging
from source.api.rest.routes import setup_app
from source.config import config

# DB
from source.db.connection_pool import DatabasePool
from source.db.state_repository import StateRepository
from source.db.session_repository import SessionRepository
from source.db.fund_repository import FundRepository
from source.db.book_repository import BookRepository
from source.db.user_repository import UserRepository
from source.db.conviction_repository import ConvictionRepository
from source.db.crypto_repository import CryptoRepository

# MANAGERS
from source.core.state_manager import StateManager
from source.core.session_manager import SessionManager
from source.core.fund_manager import FundManager
from source.core.book_manager import BookManager
from source.core.crypto_manager import CryptoManager
from source.core.conviction_manager import ConvictionManager

# CLIENTS
from source.clients.auth_client import AuthClient
from source.clients.exchange_client import ExchangeClient

# METRICS
from source.utils.metrics import setup_metrics
from source.utils.tracing import setup_tracing

logger = logging.getLogger('fund_service')


class GracefulExit(SystemExit):
    """Special exception for graceful exit"""
    pass


async def setup_database():
    """Initialize database connection pool with proper error handling"""
    logger.info("Setting up database connection...")
    
    try:
        # Create DatabasePool instance
        db_pool = DatabasePool()
        
        # Initialize the pool (this now exists and handles retries)
        await db_pool.initialize()
        
        # Verify connection works
        health = await db_pool.health_check()
        if health['status'] != 'healthy':
            raise RuntimeError(f"Database health check failed: {health.get('error', 'Unknown error')}")
        
        logger.info("Database connection pool created and verified successfully")
        return db_pool
        
    except Exception as e:
        logger.error(f"Failed to create database pool: {e}")
        raise


async def setup_dependencies():
    """Setup all service dependencies with proper error handling"""
    logger.info("Setting up service dependencies...")
    
    dependencies = {}
    
    try:
        # Initialize database first
        dependencies['db_pool'] = await setup_database()
        
        # Initialize repositories
        logger.info("Initializing repositories...")
        dependencies['state_repository'] = StateRepository()
        dependencies['session_repository'] = SessionRepository()
        dependencies['fund_repository'] = FundRepository()
        dependencies['book_repository'] = BookRepository()
        dependencies['user_repository'] = UserRepository()
        dependencies['conviction_repository'] = ConvictionRepository()
        dependencies['crypto_repository'] = CryptoRepository()
        
        # Initialize API clients
        logger.info("Initializing API clients...")
        dependencies['auth_client'] = AuthClient(config.auth_service_url)
        dependencies['exchange_client'] = ExchangeClient()
        
        # Initialize managers in the correct dependency order
        logger.info("Initializing service managers...")
        dependencies['state_manager'] = StateManager(dependencies['state_repository'])
        dependencies['session_manager'] = SessionManager(
            dependencies['session_repository'],
            dependencies['auth_client']
        )
        dependencies['crypto_manager'] = CryptoManager(dependencies['crypto_repository'])
        
        # BookManager requires crypto_manager and user_repository
        dependencies['book_manager'] = BookManager(
            dependencies['book_repository'],
            dependencies['user_repository'],
            dependencies['crypto_manager']
        )
        
        dependencies['fund_manager'] = FundManager(
            dependencies['fund_repository'],
            dependencies['crypto_manager']
        )
        
        # ConvictionManager requires ALL these dependencies (this was the missing piece!)
        dependencies['conviction_manager'] = ConvictionManager(
            dependencies['conviction_repository'],  # conviction_repository
            dependencies['book_manager'],           # book_manager  
            dependencies['crypto_manager'],         # crypto_manager
            dependencies['session_manager'],        # session_manager
            dependencies['exchange_client']         # exchange_client
        )
        
        logger.info("All service dependencies initialized successfully")
        return dependencies
        
    except Exception as e:
        logger.error(f"Failed to setup dependencies: {e}")
        # Clean up any partially initialized dependencies
        await cleanup_dependencies(dependencies)
        raise


async def cleanup_dependencies(dependencies: dict):
    """Clean up service dependencies"""
    logger.info("Cleaning up service dependencies...")
    
    # Close API clients
    for client_name in ['auth_client', 'exchange_client']:
        if client_name in dependencies:
            try:
                await dependencies[client_name].close()
                logger.info(f"Closed {client_name}")
            except Exception as e:
                logger.error(f"Error closing {client_name}: {e}")
    
    # Close managers (if they have close methods)
    for manager_name in ['book_manager', 'fund_manager', 'session_manager', 'conviction_manager']:
        if manager_name in dependencies:
            try:
                manager = dependencies[manager_name]
                if hasattr(manager, 'close'):
                    await manager.close()
                    logger.info(f"Closed {manager_name}")
            except Exception as e:
                logger.error(f"Error closing {manager_name}: {e}")
    
    # Close database pool last
    if 'db_pool' in dependencies:
        try:
            await dependencies['db_pool'].close()
            logger.info("Closed database pool")
        except Exception as e:
            logger.error(f"Error closing database pool: {e}")
    
    logger.info("Service dependencies cleanup complete")


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        raise GracefulExit()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Initialize and run the fund service"""
    # Setup logging
    setup_logging()
    logger.info("Starting fund service")
    
    # Setup signal handlers
    setup_signal_handlers()

    # Initialize tracing
    if config.enable_tracing:
        setup_tracing()
        logger.info("Distributed tracing initialized")

    # Initialize metrics
    if config.enable_metrics:
        setup_metrics()
        logger.info("Metrics initialized")

    dependencies = None
    runner = None
    site = None
    
    try:
        # Setup dependencies
        dependencies = await setup_dependencies()
        
        # Create REST API app with database pool
        app, runner, site = await setup_app(
            dependencies['state_manager'],
            dependencies['session_manager'],
            dependencies['fund_manager'],
            dependencies['book_manager'],
            dependencies['conviction_manager'],
            dependencies['db_pool']  # Pass db_pool for health checks
        )
        
        logger.info(f"Fund service started successfully on {config.host}:{config.rest_port}")
        
        # Keep the service running
        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, GracefulExit):
            logger.info("Received shutdown signal, shutting down gracefully...")
        
    except Exception as e:
        logger.error(f"Failed to start fund service: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        if site:
            try:
                await site.stop()
                logger.info("TCP site stopped")
            except Exception as e:
                logger.error(f"Error stopping TCP site: {e}")
                
        if runner:
            try:
                await runner.cleanup()
                logger.info("REST API runner cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning up REST API runner: {e}")
        
        if dependencies:
            await cleanup_dependencies(dependencies)
        
        logger.info("Fund service shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Fund service interrupted")
    except Exception as e:
        logger.error(f"Fund service crashed: {e}")
        sys.exit(1)