"""
Session manager for handling user sessions.
Coordinates the core components for session and simulator management.
"""
import logging

from opentelemetry import trace

from source.db.stores.postgres.postgres_session_store import PostgresSessionStore
from source.db.stores.redis.redis_session_cache import RedisSessionCache
from source.db.stores.redis.redis_pubsub import RedisPubSub

from source.api.clients.auth_client import AuthClient
from source.api.clients.exchange_client import ExchangeClient

from source.core.session.session_operations import SessionOperations
from source.core.session.session_simulator_operations import SimulatorOperations
from source.core.session.utils.reconnection_handler import ReconnectionHandler
from source.core.session.utils.connection_quality import ConnectionQualityManager
from source.core.session.session_tasks import SessionTasks

logger = logging.getLogger('session_manager')


class SessionManager:
    """Manager for user sessions - coordinates all session-related operations"""

    def __init__(
        self,
        postgres_store: PostgresSessionStore,
        redis_cache: RedisSessionCache,
        redis_pubsub: RedisPubSub,
        auth_client: AuthClient,
        exchange_client: ExchangeClient,
    ):
        """
        Initialize session manager and its component modules

        Args:
            db_manager: Database manager for session persistence
            auth_client: Authentication client for token validation
            exchange_client: Exchange client for simulator communication
            redis_client: Optional Redis client for pub/sub and caching
        """
        self.postgres_store = postgres_store
        self.redis_cache = redis_cache
        self.redis_pubsub = redis_pubsub

        self.auth_client = auth_client
        self.exchange_client = exchange_client

        # Initialize component modules
        self.session_ops = SessionOperations(self)
        self.simulator_ops = SimulatorOperations(self)
        self.reconnection = ReconnectionHandler(self)
        self.connection_quality = ConnectionQualityManager(self)
        self.tasks = SessionTasks(self)

        # Background tasks
        self.cleanup_task = None
        self.heartbeat_task = None

        # Create tracer
        self.tracer = trace.get_tracer("session_manager")

    async def create_session(self, user_id, device_id, token, ip_address=None):
        """Delegate to session operations"""
        return await self.session_ops.create_session(user_id, device_id, token, ip_address)

    async def get_session(self, session_id):
        """Delegate to session operations"""
        return await self.session_ops.get_session(session_id)

    async def update_session_activity(self, session_id):
        """Delegate to session operations"""
        return await self.session_ops.update_session_activity(session_id)

    async def update_session_metadata(self, session_id: str, metadata_updates: Dict[str, Any]) -> bool:
        """
        Update session metadata in PostgreSQL.
        """
        # Metadata is primarily stored in PostgreSQL
        with optional_trace_span(self.tracer, "manager_update_session_metadata") as span:
            span.set_attribute("session_id", session_id)
            success = await self.postgres_store.update_session_metadata(session_id, metadata_updates)
            # Optionally, publish an event if metadata changes are significant
            # try:
            #     if success:
            #         await self.redis_pubsub.publish_event('session_metadata_updated', {'session_id': session_id, 'updates': metadata_updates})
            # except Exception as e:
            #     logger.warning(f"Redis publish_event (session_metadata_updated) failed for {session_id}: {e}")
            return success

    async def end_session(self, session_id, token):
        """Delegate to session operations"""
        return await self.session_ops.end_session(session_id, token)

    async def start_exchange_stream(self, session_id, token=None):
        """Delegate to simulator operations"""
        return await self.simulator_ops.start_exchange_stream(session_id, token)

    async def update_connection_quality(self, session_id, token, metrics):
        """Delegate to connection quality manager"""
        return await self.connection_quality.update_connection_quality(session_id, token, metrics)

    async def reconnect_session(self, session_id, token, device_id, attempt=1):
        """Delegate to reconnection handler"""
        return await self.reconnection.reconnect_session(session_id, token, device_id, attempt)
