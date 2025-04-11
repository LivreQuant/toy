# data_access/connection_manager.py
"""
Centralized connection management for databases.
"""
import logging

from source.db.stores.postgres.postgres_session_store import PostgresSessionStore
from source.db.stores.postgres.postgres_simulator_store import PostgresSimulatorStore

from source.db.stores.redis.redis_session_cache import RedisSessionCache
from source.db.stores.redis.redis_pubsub import RedisPubSub
from source.db.stores.redis.redis_coordination import RedisCoordinationStore

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages connections for all database stores.
    Provides centralized connect/close/check methods.
    """

    def __init__(self):
        """
        Initialize connection manager with store instances.

        Stores are initialized but not connected until connect() is called.
        """
        # PostgreSQL Stores
        self.postgres_session_store = PostgresSessionStore()
        self.postgres_simulator_store = PostgresSimulatorStore()

        # Redis Stores
        self.redis_session_cache = RedisSessionCache()
        self.redis_pubsub = RedisPubSub()
        self.redis_coordination = RedisCoordinationStore()

        # Collect all stores for easier management
        self._stores = [
            self.postgres_session_store,
            self.postgres_simulator_store,
            self.redis_session_cache,
            self.redis_pubsub,
            self.redis_coordination
        ]

    async def connect(self):
        """
        Connect to all configured databases.

        Attempts to connect to each store, logging any connection failures.
        Does not raise exceptions to allow partial connectivity.
        """
        logger.info("Connecting to all database stores...")

        for store in self._stores:
            try:
                await store.connect()
                logger.info(f"Successfully connected to {store.__class__.__name__}")
            except Exception as e:
                logger.error(f"Failed to connect to {store.__class__.__name__}: {e}")

    async def close(self):
        """
        Close all database connections.

        Attempts to close each store's connection, logging any close failures.
        """
        logger.info("Closing all database store connections...")

        for store in self._stores:
            try:
                await store.close()
                logger.info(f"Successfully closed {store.__class__.__name__}")
            except Exception as e:
                logger.error(f"Failed to close {store.__class__.__name__}: {e}")

    async def check_connection(self) -> bool:
        """
        Check connection health for all stores.

        Returns True if all critical stores are healthy.
        """
        logger.info("Performing database connection health check...")

        # Postgres stores are critical
        postgres_healthy = (
                await self.postgres_session_store.check_connection() and
                await self.postgres_simulator_store.check_connection()
        )

        # Redis stores are important but not critical
        redis_healthy = (
                await self.redis_session_cache.check_connection() and
                await self.redis_pubsub.check_connection() and
                await self.redis_coordination.check_connection()
        )

        if not postgres_healthy:
            logger.critical("Critical PostgreSQL stores are not healthy!")
            return False

        if not redis_healthy:
            logger.warning("Some Redis stores are not healthy. Functionality may be limited.")

        return True
    