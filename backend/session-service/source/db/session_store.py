# source/db/session_store.py
"""
Database access layer for session management.
Coordinates PostgreSQL for persistent storage and Redis for caching/real-time.
"""
import logging
from typing import Dict, List, Any, Optional, Tuple

from opentelemetry import trace

from source.config import config

from source.utils.tracing import optional_trace_span

from source.models.session import Session, SessionStatus, SessionMetadata
from source.models.simulator import Simulator, SimulatorStatus

from source.db.postgres_store import PostgresStore
from source.db.redis_store import RedisStore

logger = logging.getLogger('session_store')


class DatabaseManager:
    """Coordinates PostgreSQL and Redis storage for session service"""

    def __init__(self):
        """Initialize database manager"""
        self.postgres = PostgresStore()
        self.redis = RedisStore()
        self.tracer = trace.get_tracer("db_manager")

    async def connect(self):
        """Connect to both databases"""
        # Connect to PostgreSQL (primary data store)
        await self.postgres.connect()
        logger.info("Connected to database")

        # Try to connect to Redis (may continue if Redis is not available)
        try:
            await self.redis.connect()
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Some features may be limited.")

    async def close(self):
        """Close database connections"""
        await self.postgres.close()
        await self.redis.close()
        logger.info("Closed database connections")

    async def check_connection(self) -> bool:
        """Check database connection health"""
        # Primary check is PostgreSQL (required for operation)
        pg_healthy = await self.postgres.check_connection()

        # Redis check (optional, service can run with limited functionality)
        redis_healthy = await self.redis.check_connection()

        if not redis_healthy:
            logger.warning("Redis connection check failed. Some features may be limited.")

        # Overall health depends primarily on PostgreSQL
        return pg_healthy

    # Session operations
    async def create_session(self, user_id: str, ip_address: Optional[str] = None) -> Tuple[str, bool]:
        """
        Create a new session for a user
        
        Returns:
            Tuple of (session_id, is_new)
        """
        with optional_trace_span(self.tracer, "create_session") as span:
            # Primary storage in PostgreSQL
            session_id, is_new = await self.postgres.create_session(user_id, ip_address)

            if session_id:
                span.set_attribute("session_id", session_id)
                span.set_attribute("is_new", is_new)

                # Cache in Redis for fast access
                try:
                    ttl_seconds = config.session.timeout_seconds
                    await self.redis.cache_session(session_id, user_id, ttl_seconds)

                    # Publish event via Redis
                    await self.redis.publish_session_event('session_created', {
                        'session_id': session_id,
                        'user_id': user_id
                    })
                except Exception as e:
                    # Log but continue - Redis is secondary
                    logger.warning(f"Redis operations failed during session creation: {e}")

            return session_id, is_new

    async def get_session_from_db(self, session_id: str) -> Optional[Session]:
        """
        Get a session by ID, first trying Redis, then falling back to PostgreSQL
        """
        with optional_trace_span(self.tracer, "get_session") as span:
            span.set_attribute("session_id", session_id)

            # Always get from PostgreSQL for complete data
            session = await self.postgres.get_session_from_db(session_id)

            if session:
                # Update Redis cache
                try:
                    ttl_seconds = config.session.timeout_seconds
                    await self.redis.cache_session(session_id, session.user_id, ttl_seconds)
                except Exception as e:
                    # Non-critical error
                    logger.debug(f"Redis cache update failed for session {session_id}: {e}")

            return session

    async def update_session_metadata(self, session_id: str, metadata_updates: Dict[str, Any]) -> bool:
        """
        Update session metadata
        """
        # Update in PostgreSQL (primary)
        success = await self.postgres.update_session_metadata(session_id, metadata_updates)

        # No specific Redis updates needed for metadata - it's primarily accessed from PostgreSQL

        return success

    async def update_session_activity(self, session_id: str) -> bool:
        """
        Update session activity time
        """
        # Update in PostgreSQL (primary)
        success = await self.postgres.update_session_activity(session_id)

        # Also update Redis TTL/activity
        try:
            ttl_seconds = config.session.timeout_seconds
            await self.redis.update_session_activity(session_id, ttl_seconds)
        except Exception as e:
            # Non-critical error
            logger.debug(f"Redis activity update failed for session {session_id}: {e}")

        return success

    async def update_session_status(self, session_id: str, status: str) -> bool:
        """
        Update session status
        """
        # Update in PostgreSQL (primary)
        success = await self.postgres.update_session_status(session_id, status)

        # If marking as EXPIRED, invalidate in Redis
        if status == SessionStatus.EXPIRED.value:
            try:
                # Get user ID from Redis cache if available, otherwise from PostgreSQL
                user_id = await self.redis.get_session_user(session_id)
                if not user_id:
                    session = await self.postgres.get_session_from_db(session_id)
                    user_id = session.user_id if session else None

                # Invalidate the session in Redis
                await self.redis.invalidate_session(session_id, user_id)

                # Publish event via Redis
                await self.redis.publish_session_event('session_ended', {
                    'session_id': session_id,
                    'user_id': user_id
                })
            except Exception as e:
                # Non-critical error
                logger.debug(f"Redis session invalidation failed for {session_id}: {e}")

        return success

    async def get_sessions_with_criteria(self, criteria: Dict[str, Any]) -> List[Session]:
        """
        Get sessions matching criteria
        """
        # This is a search operation - use PostgreSQL directly
        return await self.postgres.get_sessions_with_criteria(criteria)

    async def get_active_user_sessions(self, user_id: str) -> List[Session]:
        """
        Get active sessions for a user
        """
        # Primary data from PostgreSQL
        return await self.postgres.get_active_user_sessions(user_id)

    async def get_active_session_count(self) -> int:
        """
        Get count of active sessions
        """
        return await self.postgres.get_active_session_count()

    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions
        """
        # Primary cleanup in PostgreSQL
        count = await self.postgres.cleanup_expired_sessions()

        # Redis cleanup happens automatically via key expiration

        return count

    # Simulator operations
    async def create_simulator(self, simulator: Simulator) -> bool:
        """
        Create a new simulator
        """
        success = await self.postgres.create_simulator(simulator)

        if success:
            # Publish event via Redis
            try:
                await self.redis.publish_session_event('simulator_created', {
                    'simulator_id': simulator.simulator_id,
                    'session_id': simulator.session_id,
                    'user_id': simulator.user_id
                })
            except Exception as e:
                # Non-critical error
                logger.debug(f"Redis event publishing failed for simulator creation: {e}")

        return success

    async def update_simulator_endpoint(self, simulator_id: str, endpoint: str) -> bool:
        """
        Update simulator endpoint
        """
        return await self.postgres.update_simulator_endpoint(simulator_id, endpoint)

    async def update_simulator_status(self, simulator_id: str, status: SimulatorStatus) -> bool:
        """
        Update simulator status
        """
        success = await self.postgres.update_simulator_status(simulator_id, status)

        if success and status == SimulatorStatus.STOPPED:
            # Get simulator info for event publishing
            simulator = await self.postgres.get_simulator(simulator_id)
            if simulator:
                # Publish event via Redis
                try:
                    await self.redis.publish_session_event('simulator_stopped', {
                        'simulator_id': simulator_id,
                        'session_id': simulator.session_id,
                        'user_id': simulator.user_id
                    })
                except Exception as e:
                    # Non-critical error
                    logger.debug(f"Redis event publishing failed for simulator stop: {e}")

        return success

    async def get_simulator(self, simulator_id: str) -> Optional[Simulator]:
        """
        Get simulator by ID
        """
        return await self.postgres.get_simulator(simulator_id)

    async def get_simulator_by_session(self, session_id: str) -> Optional[Simulator]:
        """
        Get simulator for a session
        """
        return await self.postgres.get_simulator_by_session(session_id)

    async def get_active_user_simulators(self, user_id: str) -> List[Simulator]:
        """
        Get active simulators for a user
        """
        return await self.postgres.get_active_user_simulators(user_id)

    async def get_all_simulators(self) -> List[Simulator]:
        """
        Get all simulators
        """
        return await self.postgres.get_all_simulators()

    async def get_active_simulator_count(self) -> int:
        """
        Get count of active simulators
        """
        return await self.postgres.get_active_simulator_count()

    async def update_simulator_last_active(self, simulator_id: str, timestamp: float) -> bool:
        """
        Update simulator last active time
        """
        return await self.postgres.update_simulator_last_active(simulator_id, timestamp)

    async def cleanup_inactive_simulators(self, inactivity_timeout: int) -> int:
        """
        Clean up inactive simulators
        """
        return await self.postgres.cleanup_inactive_simulators(inactivity_timeout)

    # Redis-specific operations
    async def register_pubsub_handler(self, event_type: str, handler_func):
        """
        Register a handler for Redis pub/sub events
        """
        self.redis.register_pubsub_handler(event_type, handler_func)

    async def subscribe_to_events(self, callback):
        """
        Subscribe to all Redis events
        """
        return self.redis.subscribe_to_events(callback)

    async def publish_event(self, event_type: str, data: Dict[str, Any]) -> bool:
        """
        Publish event to Redis pub/sub
        """
        return await self.redis.publish_session_event(event_type, data)

    async def acquire_distributed_lock(self, lock_name: str, ttl_seconds: int = 30) -> bool:
        """
        Acquire a distributed lock via Redis
        """
        return await self.redis.acquire_lock(lock_name, ttl_seconds)

    async def release_distributed_lock(self, lock_name: str) -> bool:
        """
        Release a distributed lock via Redis
        """
        return await self.redis.release_lock(lock_name)

    # WebSocket connection tracking via Redis
    async def track_websocket_connection(self, session_id: str, client_id: str) -> bool:
        """
        Track WebSocket connection in Redis
        """
        try:
            return await self.redis.track_websocket_connection(session_id, client_id)
        except Exception as e:
            logger.warning(f"Failed to track WebSocket in Redis: {e}")
            return False

    async def remove_websocket_connection(self, session_id: str, client_id: str) -> bool:
        """
        Remove WebSocket connection tracking from Redis
        """
        try:
            return await self.redis.remove_websocket_connection(session_id, client_id)
        except Exception as e:
            logger.warning(f"Failed to remove WebSocket from Redis: {e}")
            return False

    async def get_session_websocket_connections(self, session_id: str) -> List[str]:
        """
        Get all WebSocket client IDs for a session from Redis
        """
        try:
            return await self.redis.get_session_websocket_connections(session_id)
        except Exception as e:
            logger.warning(f"Failed to get session WebSockets from Redis: {e}")
            return []
