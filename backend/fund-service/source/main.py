# source/main.py
import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager

import asyncpg
import uvloop
from aiohttp import web

from source.config import config
from source.api.rest.routes import setup_app
from source.db.state_repository import StateRepository
from source.db.fund_repository import FundRepository
from source.db.book_repository import BookRepository
from source.db.conviction_repository import ConvictionRepository
from source.clients.auth_client import AuthClient
from source.core.state_manager import StateManager
from source.core.session_manager import SessionManager
from source.core.fund_manager import FundManager
from source.core.book_manager import BookManager
from source.core.conviction_manager import ConvictionManager
from source.core.crypto_manager import CryptoManager

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('fund_service')

async def setup_database():
    """Initialize database connection pool"""
    logger.info("Setting up database connection...")
    
    try:
        pool = await asyncpg.create_pool(
            host=config.db_host,
            port=config.db_port,
            database=config.db_name,
            user=config.db_user,
            password=config.db_password,
            min_size=config.db_min_connections,
            max_size=config.db_max_connections,
            command_timeout=60
        )
        
        logger.info("Database connection pool created successfully")
        return pool
        
    except Exception as e:
        logger.error(f"Failed to create database pool: {e}")
        raise

# source/main.py (update setup_dependencies function)
async def setup_dependencies():
    """Initialize all service dependencies"""
    logger.info("Setting up service dependencies...")
    
    # Database setup
    db_pool = await setup_database()
    
    # Repositories
    state_repository = StateRepository(db_pool)
    fund_repository = FundRepository(db_pool)
    book_repository = BookRepository(db_pool)
    user_repository = UserRepository(db_pool)  # NEW
    conviction_repository = ConvictionRepository(db_pool)
    
    # Clients
    auth_client = AuthClient()
    
    # Crypto manager
    crypto_manager = CryptoManager()
    
    # Managers
    state_manager = StateManager(state_repository)
    session_manager = SessionManager(auth_client)
    fund_manager = FundManager(fund_repository, crypto_manager)
    book_manager = BookManager(book_repository, crypto_manager, user_repository)  # UPDATED
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
        'crypto_manager': crypto_manager,
        'user_repository': user_repository  # NEW
    }

async def cleanup_dependencies(dependencies):
    """Clean up service dependencies"""
    logger.info("Cleaning up service dependencies...")
    
    # Close clients
    if 'auth_client' in dependencies:
        await dependencies['auth_client'].close()
    
    if 'book_manager' in dependencies:
        await dependencies['book_manager'].close()
    
    # Close database pool
    if 'db_pool' in dependencies:
        await dependencies['db_pool'].close()
    
    logger.info("Service dependencies cleaned up")

@asynccontextmanager
async def lifespan_context():
    """Application lifespan context manager"""
    dependencies = None
    try:
        # Setup
        dependencies = await setup_dependencies()
        yield dependencies
    finally:
        # Cleanup
        if dependencies:
            await cleanup_dependencies(dependencies)

async def create_application():
    """Create and configure the web application"""
    async with lifespan_context() as dependencies:
        # Create REST API app
        app, runner = await setup_app(
            dependencies['state_manager'],
            dependencies['session_manager'],
            dependencies['fund_manager'],
            dependencies['book_manager'],
            dependencies['conviction_manager']
        )
        
        return app, runner, dependencies

def setup_signal_handlers(dependencies):
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(cleanup_dependencies(dependencies))
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

async def main():
    """Main application entry point"""
    logger.info("Starting Fund Service...")
    
    # Set event loop policy for better performance
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    
    try:
        # Create application with dependencies
        app, runner, dependencies = await create_application()
        
        # Setup signal handlers
        setup_signal_handlers(dependencies)
        
        # Start the web server
        logger.info(f"Starting web server on {config.host}:{config.rest_port}")
        await runner.setup()
        site = web.TCPSite(runner, config.host, config.rest_port)
        await site.start()
        
        logger.info(f"Fund Service started successfully on {config.host}:{config.rest_port}")
        
        # Keep the service running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")
        
    except Exception as e:
        logger.error(f"Failed to start Fund Service: {e}")
        raise
    finally:
        logger.info("Fund Service shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())