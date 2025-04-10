"""
Session manager for handling user sessions.
Coordinates the core components for session and simulator management.
"""
import logging
import asyncio

from opentelemetry import trace
from source.db.session_store import DatabaseManager
from source.api.clients.auth_client import AuthClient
from source.api.clients.exchange_client import ExchangeClient
from source.core.simulator.simulator_manager import SimulatorManager
from source.config import config

from source.core.session.session_operations import SessionOperations
from source.core.session.session_simulator_operations import SimulatorOperations
from source.core.session.reconnection_handler import ReconnectionHandler
from source.core.session.connection_quality import ConnectionQualityManager
from source.core.session.session_tasks import SessionTasks

logger = logging.getLogger('session_manager')


class SessionManager:
    """Manager for user sessions - coordinates all session-related operations"""

    def __init__(
            self,
            db_manager: DatabaseManager,
            auth_client: AuthClient,
            exchange_client: ExchangeClient,
            websocket_manager=None
    ):
        """
        Initialize session manager and its component modules

        Args:
            db_manager: Database manager for session persistence
            auth_client: Authentication client for token validation
            exchange_client: Exchange client for simulator communication
            redis_client: Optional Redis client for pub/sub and caching
            websocket_manager: WebSocket manager instance for notifications
        """
        self.db_manager = db_manager
        self.auth_client = auth_client
        self.exchange_client = exchange_client
        self.websocket_manager = websocket_manager
        self.pod_name = config.kubernetes.pod_name

        # Create simulator manager
        self.simulator_manager = SimulatorManager(db_manager, exchange_client)

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

    async def start_session_tasks(self):
        """Start background cleanup task and simulator heartbeat task"""
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self.tasks.run_cleanup_loop())
            logger.info("Started session cleanup task.")

        if self.heartbeat_task is None or self.heartbeat_task.done():
            self.heartbeat_task = asyncio.create_task(self.tasks.run_simulator_heartbeat_loop())
            logger.info("Started simulator heartbeat task.")

    async def stop_cleanup_task(self):
        """Stop background cleanup task and heartbeat task"""
        logger.info("Stopping background tasks (cleanup, heartbeat)...")
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                logger.info("Session cleanup task cancelled.")
            except Exception as e:
                logger.error(f"Error awaiting cancelled cleanup task: {e}")
            self.cleanup_task = None

        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                logger.info("Simulator heartbeat task cancelled.")
            except Exception as e:
                logger.error(f"Error awaiting cancelled heartbeat task: {e}")
            self.heartbeat_task = None
        logger.info("Background tasks stopped.")

    # Delegate methods to appropriate components for backward compatibility

    async def get_user_from_token(self, token: str):
        """Delegate to session operations"""
        return await self.session_ops.get_user_from_token(token)

    async def create_session(self, user_id, device_id, token, ip_address=None):
        """Delegate to session operations"""
        return await self.session_ops.create_session(user_id, device_id, token, ip_address)

    async def get_session(self, session_id):
        """Delegate to session operations"""
        return await self.session_ops.get_session(session_id)

    async def validate_session(self, session_id, token, device_id=None):
        """Delegate to session operations"""
        return await self.session_ops.validate_session(session_id, token, device_id)

    async def update_session_activity(self, session_id):
        """Delegate to session operations"""
        return await self.session_ops.update_session_activity(session_id)

    async def end_session(self, session_id, token):
        """Delegate to session operations"""
        return await self.session_ops.end_session(session_id, token)

    async def start_simulator(self, session_id, token):
        """Delegate to simulator operations"""
        return await self.simulator_ops.start_simulator(session_id, token)

    async def stop_simulator(self, session_id, token=None, force=False):
        """Delegate to simulator operations"""
        return await self.simulator_ops.stop_simulator(session_id, token, force)

    async def start_exchange_stream(self, session_id, token=None):
        """Delegate to simulator operations"""
        return await self.simulator_ops.start_exchange_stream(session_id, token)

    async def update_connection_quality(self, session_id, token, metrics):
        """Delegate to connection quality manager"""
        return await self.connection_quality.update_connection_quality(session_id, token, metrics)

    async def reconnect_session(self, session_id, token, device_id, attempt=1):
        """Delegate to reconnection handler"""
        return await self.reconnection.reconnect_session(session_id, token, device_id, attempt)

    async def transfer_session_ownership(self, session_id, new_pod_name):
        """Delegate to reconnection handler"""
        return await self.reconnection.transfer_session_ownership(session_id, new_pod_name)
