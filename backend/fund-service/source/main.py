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
    """Initialize database connection pool"""
    logger.info("Setting up database connection...")
    
    try:
        # Use the DatabasePool from connection_pool module
        db_pool = DatabasePool()
        await db_pool.initialize()
        
        logger.info("Database connection pool created successfully")
        return db_pool
        
    except Exception as e:
        logger.error(f"Failed to create database pool: {e}")
        raise


async def setup_dependencies():
    """Initialize all service dependencies"""
    logger.info("Setting up service dependencies...")
    
    # Database setup
    db_pool = await setup_database()
    
    # Repositories
    state_repository = StateRepository(db_pool)
    fund_repository = FundRepository(db_pool)
    book_repository = BookRepository(db_pool)
    user_repository = UserRepository(db_pool)
    conviction_repository = ConvictionRepository(db_pool)
    crypto_repository = CryptoRepository(db_pool)
    
    # Clients
    auth_client = AuthClient()
    exchange_client = ExchangeClient()
    
    # Crypto manager
    crypto_manager = CryptoManager(crypto_repository)
    
    # Managers
    state_manager = StateManager(state_repository)
    session_manager = SessionManager(auth_client)
    fund_manager = FundManager(fund_repository, crypto_manager)
    book_manager = BookManager(book_repository, crypto_manager, user_repository)
    conviction_manager = ConvictionManager(conviction_repository, crypto_manager)
    
    logger.info("Service dependencies initialized successfully")
    
    return {
        'db_pool': db_pool,
        'state_manager': state_manager,
        'session_manager': session_manager,
        'fund_manager': fund_manager,
        'book_manager': book_manager,
        'conviction_manager': conviction_manager,
        'auth_client': auth_client,
        'exchange_client': exchange_client,
        'crypto_manager': crypto_manager,
        'user_repository': user_repository
    }


async def cleanup_dependencies(dependencies):
    """Clean up service dependencies"""
    logger.info("Cleaning up service dependencies...")
    
    # Close clients
    if 'auth_client' in dependencies:
        await dependencies['auth_client'].close()
    
    if 'exchange_client' in dependencies:
        await dependencies['exchange_client'].close()
    
    if 'book_manager' in dependencies:
        await dependencies['book_manager'].close()
    
    # Close database pool
    if 'db_pool' in dependencies:
        await dependencies['db_pool'].close()
    
    logger.info("Service dependencies cleaned up")


async def main():
    """Initialize and run the fund service"""
    # Setup logging
    setup_logging()

    logger.info("Starting fund service")

    # Initialize tracing
    if config.enable_tracing:
        setup_tracing()
        logger.info("Distributed tracing initialized")

    # Initialize metrics
    if config.enable_metrics:
        setup_metrics()
        logger.info("Metrics initialized")

    dependencies = None
    try:
        # Setup dependencies
        dependencies = await setup_dependencies()
        
        # Create REST API app
        app, runner = await setup_app(
            dependencies['state_manager'],
            dependencies['session_manager'],
            dependencies['fund_manager'],
            dependencies['book_manager'],
            dependencies['conviction_manager']
        )
        
        logger.info(f"Fund service started successfully on {config.host}:{config.rest_port}")
        
        # Keep the service running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")
        
    except Exception as e:
        logger.error(f"Failed to start fund service: {e}")
        raise
    finally:
        if dependencies:
            await cleanup_dependencies(dependencies)
        logger.info("Fund service shutdown complete")


if __name__ == "__main__":
    # Remove uvloop dependency - use standard asyncio
    asyncio.run(main())