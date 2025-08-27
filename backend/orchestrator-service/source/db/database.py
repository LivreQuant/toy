# source/db/database.py
import asyncpg
import logging
from typing import Optional

from source.config import get_config
from source.db.base_managers.workflow_manager import WorkflowManager
from source.db.base_managers.state_manager import StateManager

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Simple database manager - just core functionality"""
    
    def __init__(self):
        self.config = get_config()
        self.pool: Optional[asyncpg.Pool] = None
        
        # Only the essential managers
        self.workflows: Optional[WorkflowManager] = None
        self.state: Optional[StateManager] = None

    async def init(self):
        """Initialize database connection and managers"""
        logger.info("🔧 Initializing database manager...")
        
        # Create connection pool
        await self._create_connection_pool()
        
        # Initialize managers
        await self._initialize_managers()
        
        logger.info("✅ Database manager initialized")

    async def _create_connection_pool(self):
        """Create database connection pool"""
        logger.info(f"🔗 Connecting to database: {self.config.DATABASE_HOST}:{self.config.DATABASE_PORT}/{self.config.DATABASE_NAME}")
        
        self.pool = await asyncpg.create_pool(
            self.config.database_url,
            min_size=self.config.DATABASE_MIN_CONNECTIONS,
            max_size=self.config.DATABASE_MAX_CONNECTIONS,
            command_timeout=30
        )
        logger.info("🔗 Database connection pool created")

    async def _initialize_managers(self):
        """Initialize only the essential managers"""
        logger.info("📋 Initializing essential data managers...")
        
        self.workflows = WorkflowManager(self)
        self.state = StateManager(self)
        
        logger.info("✅ Essential data managers initialized")

    async def close(self):
        """Close database connections"""
        if self.pool:
            await self.pool.close()
            logger.info("🔌 Database connections closed")

    async def health_check(self) -> bool:
        """Simple health check"""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            logger.error(f"❌ Database health check failed: {e}")
            return False